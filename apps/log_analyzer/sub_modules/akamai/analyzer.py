"""Akamai metrics calculation and anomaly detection."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import structlog

from apps.log_analyzer.config import LogAnalyzerConfig
from apps.log_analyzer.sub_modules.akamai.schemas import (
    AkamaiAnomaly,
    AkamaiLogEntry,
    AkamaiMetrics,
)

logger = structlog.get_logger(__name__)


class AkamaiAnalyzer:
    def __init__(self, config: LogAnalyzerConfig) -> None:
        self._config = config

    def calculate_metrics(self, logs: list[AkamaiLogEntry]) -> AkamaiMetrics:
        """Compute all AkamaiMetrics fields from parsed log entries."""
        if not logs:
            return AkamaiMetrics()

        total = len(logs)
        error_count = sum(1 for e in logs if e.status_code and e.status_code >= 400)
        # cache_hit is 0/1 int indicator; fallback to cache_status == 1 for old CSV data
        cache_hits = sum(1 for e in logs if e.cache_hit == 1 or (e.cache_hit is None and e.cache_status == 1))
        cacheable_count = sum(1 for e in logs if e.cache_hit is not None or e.cache_status is not None)
        total_bytes = sum(e.bytes or 0 for e in logs)

        # TTFB: use transfer_time_ms directly
        ttfb_values = sorted([e.transfer_time_ms for e in logs if e.transfer_time_ms is not None])
        avg_ttfb = sum(ttfb_values) / len(ttfb_values) if ttfb_values else 0.0
        p99_ttfb = ttfb_values[int(len(ttfb_values) * 0.99)] if ttfb_values else 0.0

        # Status breakdown
        status_counter: Counter[int] = Counter()
        for e in logs:
            if e.status_code:
                status_counter[e.status_code] += 1

        # Error codes
        error_paths: Counter[str] = Counter()
        for e in logs:
            if e.status_code and e.status_code >= 400 and e.error_code:
                error_paths[e.error_code] += 1
        top_errors = [
            {"code": code, "count": cnt, "pct": round(cnt / total * 100, 2)}
            for code, cnt in error_paths.most_common(20)
        ]

        # Edge breakdown (from edge_ip field)
        edge_counter: Counter[str] = Counter()
        edge_errors: Counter[str] = Counter()
        for e in logs:
            if e.edge_ip:
                edge_counter[e.edge_ip] += 1
                if e.status_code and e.status_code >= 400:
                    edge_errors[e.edge_ip] += 1
        edge_breakdown = [
            {"edge": edge, "requests": cnt, "errors": edge_errors.get(edge, 0)}
            for edge, cnt in edge_counter.most_common(10)
        ]

        # Geo breakdown
        geo_counter: Counter[str] = Counter()
        for e in logs:
            if e.country:
                geo_counter[e.country] += 1
        geo_breakdown = [{"country": c, "requests": cnt} for c, cnt in geo_counter.most_common(20)]

        # Content type breakdown (from content_type field)
        content_counter: Counter[str] = Counter()
        for e in logs:
            if e.content_type:
                content_counter[e.content_type] += 1

        # City breakdown
        city_counter: Counter[str] = Counter()
        for e in logs:
            if e.city:
                city_counter[e.city] += 1
        city_breakdown = [{"city": c, "requests": cnt} for c, cnt in city_counter.most_common(20)]

        # Peak hours
        hour_counter: Counter[int] = Counter()
        for e in logs:
            if e.req_time_sec:
                hour = datetime.fromtimestamp(e.req_time_sec, tz=UTC).hour
                hour_counter[hour] += 1
        peak_hours = [{"hour": h, "requests": cnt} for h, cnt in sorted(hour_counter.items())]

        return AkamaiMetrics(
            total_requests=total,
            error_rate=round(error_count / total, 4) if total else 0.0,
            cache_hit_rate=round(cache_hits / cacheable_count, 4) if cacheable_count else 0.0,
            avg_ttfb_ms=round(avg_ttfb, 2),
            p99_ttfb_ms=round(p99_ttfb, 2),
            total_bytes=total_bytes,
            top_errors=top_errors,
            edge_breakdown=edge_breakdown,
            geo_breakdown=geo_breakdown,
            status_breakdown=dict(status_counter),
            content_type_breakdown=dict(content_counter),
            city_breakdown=city_breakdown,
            peak_hours=peak_hours,
        )

    def detect_anomalies(self, metrics: AkamaiMetrics) -> list[AkamaiAnomaly]:
        """Detect anomalies based on configured thresholds."""
        anomalies: list[AkamaiAnomaly] = []

        if metrics.error_rate > self._config.anomaly_error_rate_threshold:
            anomalies.append(
                AkamaiAnomaly(
                    anomaly_type="high_error_rate",
                    severity="P1",
                    value=metrics.error_rate,
                    threshold=self._config.anomaly_error_rate_threshold,
                    description=f"Error rate {metrics.error_rate:.2%} exceeds threshold {self._config.anomaly_error_rate_threshold:.2%}",
                )
            )

        if metrics.cache_hit_rate < self._config.anomaly_cache_hit_threshold and metrics.total_requests > 0:
            anomalies.append(
                AkamaiAnomaly(
                    anomaly_type="low_cache_hit",
                    severity="P2",
                    value=metrics.cache_hit_rate,
                    threshold=self._config.anomaly_cache_hit_threshold,
                    description=f"Cache hit rate {metrics.cache_hit_rate:.2%} below threshold {self._config.anomaly_cache_hit_threshold:.2%}",
                )
            )

        if metrics.p99_ttfb_ms > self._config.anomaly_ttfb_p99_threshold_ms:
            anomalies.append(
                AkamaiAnomaly(
                    anomaly_type="high_ttfb",
                    severity="P2",
                    value=metrics.p99_ttfb_ms,
                    threshold=self._config.anomaly_ttfb_p99_threshold_ms,
                    description=f"P99 TTFB {metrics.p99_ttfb_ms:.0f}ms exceeds threshold {self._config.anomaly_ttfb_p99_threshold_ms:.0f}ms",
                )
            )

        return anomalies

    def get_period(self, logs: list[AkamaiLogEntry]) -> tuple[datetime, datetime]:
        """Get the time period covered by the log entries."""
        timestamps = [e.req_time_sec for e in logs if e.req_time_sec is not None]
        if not timestamps:
            now = datetime.now(UTC)
            return now, now
        return (
            datetime.fromtimestamp(min(timestamps), tz=UTC),
            datetime.fromtimestamp(max(timestamps), tz=UTC),
        )
