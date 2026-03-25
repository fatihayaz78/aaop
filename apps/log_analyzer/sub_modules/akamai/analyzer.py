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

# FIX 3: Error code categorization
SYSTEM_ERRORS = {
    "ERR_FIRST_BYTE_TIMEOUT", "ERR_ZERO_SIZE_OBJECT",
    "ERR_HTTP2_WIN_UPDATE_TIMEOUT", "ERR_DNS_FAIL", "ERR_CONNECT_FAIL",
}
CLIENT_ABORTS = {"ERR_CLIENT_ABORT"}
ACCESS_DENIED = {"ERR_ACCESS_DENIED"}


class AkamaiAnalyzer:
    def __init__(self, config: LogAnalyzerConfig) -> None:
        self._config = config

    def calculate_metrics(self, logs: list[AkamaiLogEntry]) -> AkamaiMetrics:
        """Compute all AkamaiMetrics fields from parsed log entries."""
        if not logs:
            return AkamaiMetrics()

        total = len(logs)

        # FIX 3: Error categorization (system errors, aborts, access denied)
        system_error_count = 0
        client_abort_count = 0
        access_denied_count = 0
        for e in logs:
            ec = e.error_code or ""
            if ec in SYSTEM_ERRORS:
                system_error_count += 1
            elif ec in CLIENT_ABORTS:
                client_abort_count += 1
            elif ec in ACCESS_DENIED:
                access_denied_count += 1

        # FIX 2: Cache hit uses cache_hit field (binary 0/1), NOT cache_status
        cache_hits = sum(1 for e in logs if e.cache_hit == 1)
        cache_total = sum(1 for e in logs if e.cache_hit is not None)

        # FIX 1: Bandwidth uses bytes field (actual transferred), NOT response_body_size
        total_bytes = sum(e.bytes or 0 for e in logs)
        total_response_body = sum(e.response_body_size or 0 for e in logs)

        # FIX 4: Transfer time from transfer_time_ms (field 15, milliseconds)
        ttfb_values = sorted([e.transfer_time_ms for e in logs if e.transfer_time_ms is not None])
        avg_ttfb = sum(ttfb_values) / len(ttfb_values) if ttfb_values else 0.0
        p99_ttfb = ttfb_values[int(len(ttfb_values) * 0.99)] if ttfb_values else 0.0

        # FIX 6: Unique client IPs (already hashed by parser)
        unique_ips = len(set(e.client_ip for e in logs if e.client_ip and e.client_ip != "-"))

        # FIX 8c: Bandwidth savings (cache efficiency)
        savings_pct = 0.0
        if total_response_body > 0:
            savings_pct = round((total_response_body - total_bytes) / total_response_body * 100, 2)

        # Status breakdown
        status_counter: Counter[int] = Counter()
        for e in logs:
            if e.status_code:
                status_counter[e.status_code] += 1

        # Error codes
        error_paths: Counter[str] = Counter()
        for e in logs:
            if e.error_code:
                error_paths[e.error_code] += 1
        top_errors = [
            {"code": code, "count": cnt, "pct": round(cnt / total * 100, 2)}
            for code, cnt in error_paths.most_common(20)
        ]

        # Edge breakdown
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

        # Content type breakdown
        content_counter: Counter[str] = Counter()
        for e in logs:
            if e.content_type:
                content_counter[e.content_type] += 1

        # FIX 8a: Segment type distribution (from req_path)
        segment_counter: Counter[str] = Counter()
        for e in logs:
            path = (e.req_path or "").lower()
            if ".m4s" in path:
                segment_counter["video_segment"] += 1
            elif ".m3u8" in path:
                segment_counter["hls_manifest"] += 1
            elif ".mpd" in path:
                segment_counter["dash_manifest"] += 1
            else:
                segment_counter["asset"] += 1

        # FIX 8b: Token error breakdown (from error_code)
        token_errors: Counter[str] = Counter()
        for e in logs:
            ec = e.error_code or ""
            if "ACCESS_DENIED" in ec and "SHORT_TOKEN" in ec:
                token_errors["token_invalid"] += 1
            elif "ACCESS_DENIED" in ec and "geo" in ec.lower():
                token_errors["geo_blocked"] += 1
            elif ec == "ERR_FIRST_BYTE_TIMEOUT":
                token_errors["origin_timeout"] += 1

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
            error_rate=round(system_error_count / total, 4) if total else 0.0,
            abort_rate=round(client_abort_count / total, 4) if total else 0.0,
            access_denied_rate=round(access_denied_count / total, 4) if total else 0.0,
            cache_hit_rate=round(cache_hits / cache_total, 4) if cache_total else 0.0,
            avg_ttfb_ms=round(avg_ttfb, 2),
            p99_ttfb_ms=round(p99_ttfb, 2),
            total_bytes=total_bytes,
            unique_client_ips=unique_ips,
            bandwidth_savings_pct=savings_pct,
            top_errors=top_errors,
            edge_breakdown=edge_breakdown,
            geo_breakdown=geo_breakdown,
            status_breakdown=dict(status_counter),
            content_type_breakdown=dict(content_counter),
            segment_type_breakdown=dict(segment_counter),
            token_error_breakdown=dict(token_errors),
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
