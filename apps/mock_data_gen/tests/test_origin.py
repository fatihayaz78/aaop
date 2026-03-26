"""Tests for Origin Server log generator."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.origin_logs.generator import OriginGenerator
from apps.mock_data_gen.generators.origin_logs.schemas import (
    FIELD_CATEGORIES,
    FIELD_DESCRIPTIONS,
    OriginLogEntry,
)


@pytest.fixture
def gen(tmp_path: Path) -> OriginGenerator:
    return OriginGenerator(output_root=tmp_path, seed=42)


class TestOriginSchema:
    def test_origin_schema_valid(self):
        """All 4 event_types validate correctly."""
        # cdn_miss
        cdn = OriginLogEntry(
            event_id="a1", event_type="cdn_miss",
            timestamp="2026-01-15T14:30:00Z",
            origin_host="origin-1.ssport.com.tr",
            request_method="GET", request_uri="/live/s_sport_1/1080/seg_1.ts",
            http_protocol="HTTP/1.1", cdn_pop="ist-01",
            medianova_req_id="req-123", status_code=200,
            response_time_ms=50, bytes_sent=500000,
        )
        assert cdn.event_type == "cdn_miss"
        assert cdn.medianova_req_id == "req-123"

        # health_check
        hc = OriginLogEntry(
            event_id="b1", event_type="health_check",
            timestamp="2026-01-15T14:30:00Z",
            origin_host="origin-2.ssport.com.tr",
            health_status="healthy", check_source="internal", latency_ms=5,
        )
        assert hc.health_status == "healthy"

        # transcoder_event
        te = OriginLogEntry(
            event_id="c1", event_type="transcoder_event",
            timestamp="2026-01-15T00:00:01Z",
            origin_host="origin-1.ssport.com.tr",
            encoder_id="enc-01", transcoder_status="started",
            input_stream="rtmp://ingest.ssport.com.tr/live/s_sport_1",
        )
        assert te.transcoder_status == "started"

        # hls_dash_fetch
        hls = OriginLogEntry(
            event_id="d1", event_type="hls_dash_fetch",
            timestamp="2026-01-15T14:30:00Z",
            origin_host="origin-1.ssport.com.tr",
            request_method="GET", request_uri="/live/s_sport_1/master.m3u8",
            manifest_type="hls_master",
        )
        assert hls.manifest_type == "hls_master"

    def test_origin_field_categories_complete(self):
        """All schema fields have categories."""
        schema_fields = set(OriginLogEntry.model_fields.keys())
        category_fields = set(FIELD_CATEGORIES.keys())
        assert schema_fields == category_fields

    def test_origin_field_descriptions_complete(self):
        """All schema fields have descriptions."""
        schema_fields = set(OriginLogEntry.model_fields.keys())
        desc_fields = set(FIELD_DESCRIPTIONS.keys())
        assert schema_fields == desc_fields


class TestOriginGenerator:
    def test_origin_cdn_miss_has_req_id(self, gen: OriginGenerator, tmp_path: Path):
        """cdn_miss events have medianova_req_id populated."""
        normal_date = date(2026, 1, 2)
        gen.generate_day(normal_date)

        records = _collect_records(tmp_path / "origin_logs", normal_date)
        cdn_miss_recs = [r for r in records if r["event_type"] == "cdn_miss"]

        assert len(cdn_miss_recs) > 0
        for r in cdn_miss_recs[:100]:
            assert r["medianova_req_id"] is not None, "cdn_miss must have medianova_req_id"

    def test_origin_health_check_frequency(self, gen: OriginGenerator, tmp_path: Path):
        """~2880 health checks per day (2 hosts x every 30s)."""
        normal_date = date(2026, 1, 2)
        gen.generate_day(normal_date)

        records = _collect_records(tmp_path / "origin_logs", normal_date)
        hc_count = sum(1 for r in records if r["event_type"] == "health_check")

        # 2 hosts × 2880 checks each = 5760, but we do 2 hosts × 24h × 120 per hour = 5760
        assert 5700 <= hc_count <= 5800, f"Health checks: {hc_count}"

    def test_origin_load_increases_on_derby(self, gen: OriginGenerator, tmp_path: Path):
        """Derby day peak hours have origin_load_pct > 70."""
        derby_date = date(2026, 3, 4)  # ElClasico
        gen_derby = OriginGenerator(output_root=tmp_path, seed=42)
        gen_derby.generate_day(derby_date)

        records = _collect_records(tmp_path / "origin_logs", derby_date)
        # Filter cdn_miss during peak hours (17-20 UTC)
        peak_miss = [
            r for r in records
            if r["event_type"] == "cdn_miss"
            and r.get("origin_load_pct") is not None
            and _hour_in_range(r["timestamp"], 17, 21)
        ]

        assert len(peak_miss) > 0
        avg_load = sum(r["origin_load_pct"] for r in peak_miss) / len(peak_miss)
        assert avg_load > 70, f"Derby peak avg origin_load: {avg_load:.1f}%"

    def test_origin_transcoder_started_on_day_begin(self, gen: OriginGenerator, tmp_path: Path):
        """Day begin has 'started' transcoder events for each channel."""
        normal_date = date(2026, 1, 2)
        gen.generate_day(normal_date)

        records = _collect_records(tmp_path / "origin_logs", normal_date)
        started = [
            r for r in records
            if r["event_type"] == "transcoder_event" and r["transcoder_status"] == "started"
        ]

        # 7 channels = 7 started events
        assert len(started) == 7, f"Started events: {len(started)}"

    def test_origin_outage_unhealthy_spike(self, tmp_path: Path):
        """Feb 28 CDN outage has unhealthy health checks."""
        gen = OriginGenerator(output_root=tmp_path, seed=42)
        outage_date = date(2026, 2, 28)
        gen.generate_day(outage_date)

        records = _collect_records(tmp_path / "origin_logs", outage_date)
        # Health checks during outage window (19:15-19:45 UTC)
        outage_hc = [
            r for r in records
            if r["event_type"] == "health_check"
            and "T19:" in r["timestamp"]
            and _minute_in_range(r["timestamp"], 15, 45)
        ]

        if outage_hc:
            unhealthy_count = sum(1 for r in outage_hc if r["health_status"] == "unhealthy")
            ratio = unhealthy_count / len(outage_hc)
            assert ratio > 0.4, f"Unhealthy ratio during outage: {ratio:.2%}"


# ── Helpers ──

def _collect_records(base_path: Path, target_date: date) -> list[dict]:
    """Read all JSONL.gz records for a given date."""
    import gzip
    import json

    records: list[dict] = []
    date_dir = base_path / target_date.strftime("%Y") / target_date.strftime("%m") / target_date.strftime("%d")
    if not date_dir.exists():
        return records

    for gz_file in date_dir.rglob("*.jsonl.gz"):
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def _hour_in_range(timestamp: str, start_h: int, end_h: int) -> bool:
    """Check if timestamp hour is within [start_h, end_h)."""
    parts = timestamp.split("T")[1].split(":")
    hour = int(parts[0])
    return start_h <= hour < end_h


def _minute_in_range(timestamp: str, start_min: int, end_min: int) -> bool:
    """Check if timestamp minute is within [start_min, end_min)."""
    parts = timestamp.split("T")[1].split(":")
    minute = int(parts[1])
    return start_min <= minute < end_min
