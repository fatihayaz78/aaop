"""Tests for API Logs + New Relic APM generators."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.api_logs.generator import APILogsGenerator
from apps.mock_data_gen.generators.api_logs.schemas import (
    FIELD_CATEGORIES as API_CATEGORIES,
    FIELD_DESCRIPTIONS as API_DESCRIPTIONS,
    APILogEntry,
)
from apps.mock_data_gen.generators.newrelic.generator import NewRelicGenerator, SERVICES
from apps.mock_data_gen.generators.newrelic.schemas import (
    FIELD_CATEGORIES as NR_CATEGORIES,
    FIELD_DESCRIPTIONS as NR_DESCRIPTIONS,
    NewRelicAPMEntry,
)


# ── Helpers ──

def _collect_records(base_path: Path, source: str, target_date: date) -> list[dict]:
    records: list[dict] = []
    date_dir = base_path / source / target_date.strftime("%Y") / target_date.strftime("%m") / target_date.strftime("%d")
    if not date_dir.exists():
        return records
    for gz_file in date_dir.rglob("*.jsonl.gz"):
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


# ══════════════════════════════════════════════════════════════════════
# API LOGS TESTS
# ══════════════════════════════════════════════════════════════════════


class TestAPISchema:
    def test_api_schema_valid(self):
        rec = APILogEntry(
            event_id="a1", timestamp="2026-01-15T14:30:00Z",
            request_id="r1", endpoint="/auth/login", method="POST",
            status_code=200, response_time_ms=200,
            device_type="android", ip_hash="ip1", country_code="TR",
        )
        assert rec.status_code == 200

    def test_api_field_categories_complete(self):
        schema_fields = set(APILogEntry.model_fields.keys())
        assert schema_fields == set(API_CATEGORIES.keys())

    def test_api_field_descriptions_complete(self):
        schema_fields = set(APILogEntry.model_fields.keys())
        assert schema_fields == set(API_DESCRIPTIONS.keys())


class TestAPIGenerator:
    def test_api_endpoint_distribution_normal(self, tmp_path: Path):
        """token_refresh is the dominant endpoint on normal days."""
        gen = APILogsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "api_logs", date(2026, 1, 2))

        refresh_count = sum(1 for r in records if r["endpoint"] == "/auth/token/refresh")
        ratio = refresh_count / len(records)
        assert 0.35 <= ratio <= 0.50, f"token_refresh ratio: {ratio:.2%}"

    def test_api_status_200_dominant_normal(self, tmp_path: Path):
        """Normal day has 92-96% status 200."""
        gen = APILogsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "api_logs", date(2026, 1, 2))

        ok_count = sum(1 for r in records if r["status_code"] == 200)
        ratio = ok_count / len(records)
        assert 0.92 <= ratio <= 0.96, f"200 ratio: {ratio:.2%}"

    def test_api_503_spike_cdn_outage(self, tmp_path: Path):
        """Feb 28 19:20 UTC /content/stream has 503 spike."""
        gen = APILogsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))
        records = _collect_records(tmp_path, "api_logs", date(2026, 2, 28))

        # Filter /content/stream at 19:15-19:45 UTC
        stream_outage = [
            r for r in records
            if r["endpoint"] == "/content/stream"
            and "T19:" in r["timestamp"]
            and 15 <= int(r["timestamp"].split("T19:")[1][:2]) < 45
        ]

        if stream_outage:
            count_503 = sum(1 for r in stream_outage if r["status_code"] == 503)
            ratio = count_503 / len(stream_outage)
            assert ratio > 0.50, f"503 ratio during outage: {ratio:.2%}"

    def test_api_rate_limit_derby(self, tmp_path: Path):
        """Derby day has increased 429 rate on /content/stream."""
        gen_n = APILogsGenerator(output_root=tmp_path / "n", seed=42)
        gen_d = APILogsGenerator(output_root=tmp_path / "d", seed=42)

        gen_n.generate_day(date(2026, 1, 2))
        gen_d.generate_day(date(2026, 3, 4))

        normal_recs = _collect_records(tmp_path / "n", "api_logs", date(2026, 1, 2))
        derby_recs = _collect_records(tmp_path / "d", "api_logs", date(2026, 3, 4))

        normal_429 = sum(1 for r in normal_recs if r["status_code"] == 429) / len(normal_recs)
        derby_429 = sum(1 for r in derby_recs if r["status_code"] == 429) / len(derby_recs)

        assert derby_429 > normal_429, f"Derby 429 {derby_429:.3%} <= normal {normal_429:.3%}"

    def test_api_response_time_increases_derby(self, tmp_path: Path):
        """Derby day has ~2x response time vs normal."""
        gen_n = APILogsGenerator(output_root=tmp_path / "n", seed=42)
        gen_d = APILogsGenerator(output_root=tmp_path / "d", seed=42)

        gen_n.generate_day(date(2026, 1, 2))
        gen_d.generate_day(date(2026, 3, 4))

        normal_recs = _collect_records(tmp_path / "n", "api_logs", date(2026, 1, 2))
        derby_recs = _collect_records(tmp_path / "d", "api_logs", date(2026, 3, 4))

        normal_avg = sum(r["response_time_ms"] for r in normal_recs) / len(normal_recs)
        derby_avg = sum(r["response_time_ms"] for r in derby_recs) / len(derby_recs)

        assert derby_avg > normal_avg * 1.5, f"Derby avg {derby_avg:.0f}ms not > 1.5x normal {normal_avg:.0f}ms"

    def test_api_daily_volume_normal(self, tmp_path: Path):
        """Normal weekday produces 250K-310K requests."""
        gen = APILogsGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 1, 2))  # Thursday
        assert 250_000 <= count <= 310_000, f"Normal volume: {count}"

    def test_api_daily_volume_derby(self, tmp_path: Path):
        """Derby day (x10) produces 2M+ requests."""
        gen = APILogsGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 3, 4))
        assert count >= 2_000_000, f"Derby volume: {count}"


# ══════════════════════════════════════════════════════════════════════
# NEW RELIC TESTS
# ══════════════════════════════════════════════════════════════════════


class TestNewRelicSchema:
    def test_newrelic_schema_valid(self):
        for et in ("apm_transaction", "infrastructure", "error_event"):
            rec = NewRelicAPMEntry(
                event_id="n1", event_type=et,
                timestamp="2026-01-15T14:30:00Z",
            )
            assert rec.event_type == et

    def test_newrelic_field_categories_complete(self):
        schema_fields = set(NewRelicAPMEntry.model_fields.keys())
        assert schema_fields == set(NR_CATEGORIES.keys())

    def test_newrelic_field_descriptions_complete(self):
        schema_fields = set(NewRelicAPMEntry.model_fields.keys())
        assert schema_fields == set(NR_DESCRIPTIONS.keys())


class TestNewRelicGenerator:
    def test_newrelic_apm_all_services_present(self, tmp_path: Path):
        """All 5 services have apm_transaction events."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "newrelic", date(2026, 1, 2))

        apm_recs = [r for r in records if r["event_type"] == "apm_transaction"]
        services = {r["service_name"] for r in apm_recs}
        expected = set(SERVICES.keys())
        assert services == expected, f"Missing: {expected - services}"

    def test_newrelic_infra_60s_frequency(self, tmp_path: Path):
        """Each host has ~1440 infra events per day (every 60s)."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "newrelic", date(2026, 1, 2))

        infra_recs = [r for r in records if r["event_type"] == "infrastructure"]
        # Count per host
        host_counts: dict[str, int] = {}
        for r in infra_recs:
            host_counts[r["host"]] = host_counts.get(r["host"], 0) + 1

        # Each active host should have ~1440 events (24h × 60min)
        for host, count in host_counts.items():
            assert 1400 <= count <= 1500, f"{host}: {count} infra events (expected ~1440)"

    def test_newrelic_cpu_increases_derby(self, tmp_path: Path):
        """Derby peak has CPU > 70% for key services."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 4))
        records = _collect_records(tmp_path, "newrelic", date(2026, 3, 4))

        # Filter stream-packager infra during peak (19:xx UTC)
        peak_infra = [
            r for r in records
            if r["event_type"] == "infrastructure"
            and r["service_name"] == "stream-packager"
            and "T19:" in r["timestamp"]
        ]

        assert len(peak_infra) > 0
        avg_cpu = sum(r["cpu_pct"] for r in peak_infra) / len(peak_infra)
        assert avg_cpu > 70, f"Derby peak CPU: {avg_cpu:.1f}%"

    def test_newrelic_pod_count_scales_derby(self, tmp_path: Path):
        """stream-packager scales from 4 to 16 pods during derby."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 4))
        records = _collect_records(tmp_path, "newrelic", date(2026, 3, 4))

        # Before derby (10:00 UTC)
        pre = [
            r for r in records
            if r["event_type"] == "infrastructure"
            and r["service_name"] == "stream-packager"
            and "T10:" in r["timestamp"]
        ]
        # During derby (19:00 UTC)
        during = [
            r for r in records
            if r["event_type"] == "infrastructure"
            and r["service_name"] == "stream-packager"
            and "T19:" in r["timestamp"]
        ]

        if pre and during:
            pre_pods = pre[0]["pod_count"]
            during_pods = during[0]["pod_count"]
            assert during_pods > pre_pods, f"Pods: {pre_pods} → {during_pods}"
            assert during_pods >= 16, f"Expected 16 pods, got {during_pods}"

    def test_newrelic_cdn_outage_error_event(self, tmp_path: Path):
        """Feb 28 CDN outage produces CDNUpstreamException errors."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))
        records = _collect_records(tmp_path, "newrelic", date(2026, 2, 28))

        cdn_errors = [
            r for r in records
            if r["event_type"] == "error_event"
            and r["error_class"] == "CDNUpstreamException"
        ]
        assert len(cdn_errors) > 0, "No CDNUpstreamException errors on outage day"

    def test_newrelic_apdex_drops_derby(self, tmp_path: Path):
        """Derby peak has apdex < 0.85 for stream-packager."""
        gen = NewRelicGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 4))
        records = _collect_records(tmp_path, "newrelic", date(2026, 3, 4))

        peak_apm = [
            r for r in records
            if r["event_type"] == "apm_transaction"
            and r["service_name"] == "stream-packager"
            and "T19:" in r["timestamp"]
        ]

        assert len(peak_apm) > 0
        avg_apdex = sum(r["apdex_score"] for r in peak_apm) / len(peak_apm)
        assert avg_apdex < 0.85, f"Derby apdex: {avg_apdex:.3f}"
