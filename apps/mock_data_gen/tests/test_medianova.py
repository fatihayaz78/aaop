"""Tests for Medianova CDN log generator."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.medianova.generator import MedianovaGenerator
from apps.mock_data_gen.generators.medianova.schemas import (
    FIELD_CATEGORIES,
    FIELD_DESCRIPTIONS,
    MedianovaLogEntry,
)


@pytest.fixture
def gen(tmp_path: Path) -> MedianovaGenerator:
    return MedianovaGenerator(output_root=tmp_path, seed=42)


class TestMedianovaSchema:
    def test_medianova_schema_valid(self):
        """A sample record validates against MedianovaLogEntry."""
        record = MedianovaLogEntry(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            request_method="GET",
            request_uri="/live/s_sport_1/1080/seg_123.ts",
            request_time=0.012,
            scheme="https",
            http_protocol="HTTP/2.0",
            http_host="cdn.ssport.com.tr",
            http_user_agent="Mozilla/5.0",
            status=200,
            content_type="video/MP2T",
            proxy_cache_status="HIT",
            body_bytes_sent=500000,
            bytes_sent=500500,
            timestamp="2026-01-15T14:30:00Z",
            remote_addr="a1b2c3d4e5f6",
            client_port=54321,
            asn="AS9121",
            country_code="TR",
            isp="Turk Telekom",
            tcp_info_rtt=25,
            tcp_info_rtt_var=5,
            resource_uuid="660e8400-e29b-41d4-a716-446655440000",
            account_type="enterprise",
            channel="s_sport_1",
            edge_node="ist-01",
            stream_type="hls_segment",
        )
        assert record.status == 200
        assert record.proxy_cache_status == "HIT"

    def test_medianova_field_categories_complete(self):
        """All 32 schema fields are in FIELD_CATEGORIES."""
        schema_fields = set(MedianovaLogEntry.model_fields.keys())
        category_fields = set(FIELD_CATEGORIES.keys())
        assert schema_fields == category_fields, (
            f"Missing: {schema_fields - category_fields}, Extra: {category_fields - schema_fields}"
        )

    def test_medianova_field_descriptions_complete(self):
        """All 32 schema fields have descriptions."""
        schema_fields = set(MedianovaLogEntry.model_fields.keys())
        desc_fields = set(FIELD_DESCRIPTIONS.keys())
        assert schema_fields == desc_fields


class TestMedianovaGenerator:
    def test_medianova_cache_hit_ratio_normal(self, gen: MedianovaGenerator, tmp_path: Path):
        """Normal day HIT ratio is between 65-80%."""
        # Generate a normal day (no event)
        normal_date = date(2026, 1, 2)
        gen.generate_day(normal_date)

        # Read all generated records
        records = _collect_records(tmp_path / "medianova", normal_date)
        hit_count = sum(1 for r in records if r["proxy_cache_status"] == "HIT")
        ratio = hit_count / len(records)
        assert 0.65 <= ratio <= 0.80, f"HIT ratio {ratio:.2%} not in 65-80%"

    def test_medianova_cache_miss_increases_on_derby(self, gen: MedianovaGenerator, tmp_path: Path):
        """Derby day has higher MISS rate than normal."""
        normal_date = date(2026, 1, 2)
        derby_date = date(2026, 3, 4)  # ElClasico x10

        gen_normal = MedianovaGenerator(output_root=tmp_path / "n", seed=42)
        gen_derby = MedianovaGenerator(output_root=tmp_path / "d", seed=42)

        gen_normal.generate_day(normal_date)
        gen_derby.generate_day(derby_date)

        normal_recs = _collect_records(tmp_path / "n" / "medianova", normal_date)
        derby_recs = _collect_records(tmp_path / "d" / "medianova", derby_date)

        normal_miss = sum(1 for r in normal_recs if r["proxy_cache_status"] == "MISS") / len(normal_recs)
        derby_miss = sum(1 for r in derby_recs if r["proxy_cache_status"] == "MISS") / len(derby_recs)

        assert derby_miss > normal_miss, f"Derby MISS {derby_miss:.2%} <= normal MISS {normal_miss:.2%}"

    def test_medianova_outage_503_spike(self, gen: MedianovaGenerator, tmp_path: Path):
        """Feb 28 CDN outage window (19:15-19:45 UTC) has dominant 503s."""
        outage_date = date(2026, 2, 28)
        gen.generate_day(outage_date)

        records = _collect_records(tmp_path / "medianova", outage_date)
        # Filter records in the outage UTC window (19:15-19:45 UTC)
        outage_recs = [
            r for r in records
            if "T19:" in r["timestamp"] and _minute_in_range(r["timestamp"], 15, 45)
        ]

        if outage_recs:
            count_503 = sum(1 for r in outage_recs if r["status"] == 503)
            ratio_503 = count_503 / len(outage_recs)
            assert ratio_503 > 0.5, f"503 ratio during outage: {ratio_503:.2%}"

    def test_medianova_upstream_null_on_hit(self, gen: MedianovaGenerator, tmp_path: Path):
        """HIT records have null upstream_response_time."""
        normal_date = date(2026, 1, 2)
        gen.generate_day(normal_date)

        records = _collect_records(tmp_path / "medianova", normal_date)
        hit_records = [r for r in records if r["proxy_cache_status"] == "HIT"]

        assert len(hit_records) > 0
        for r in hit_records[:100]:  # sample check
            assert r["upstream_response_time"] is None, "HIT should have null upstream_time"

    def test_medianova_output_path_format(self, gen: MedianovaGenerator, tmp_path: Path):
        """5-minute file pattern is correct."""
        test_date = date(2026, 1, 2)
        gen.generate_day(test_date)

        # Check directory structure: medianova/2026/01/02/{channel}/
        base = tmp_path / "medianova" / "2026" / "01" / "02"
        assert base.exists()

        # At least one channel dir
        channel_dirs = list(base.iterdir())
        assert len(channel_dirs) > 0

        # Files should match pattern: YYYY-MM-DD-HH-MM.jsonl.gz
        for ch_dir in channel_dirs:
            files = list(ch_dir.glob("*.jsonl.gz"))
            assert len(files) > 0
            for f in files:
                assert f.name.startswith("2026-01-02-")
                assert f.name.endswith(".jsonl.gz")

    def test_medianova_daily_volume_normal(self, gen: MedianovaGenerator, tmp_path: Path):
        """Normal day produces ~40K-60K requests."""
        normal_date = date(2026, 1, 2)
        count = gen.generate_day(normal_date)
        assert 40_000 <= count <= 60_000, f"Normal day volume: {count}"

    def test_medianova_daily_volume_derby(self, tmp_path: Path):
        """Derby day (x10) produces ~400K-600K requests."""
        gen = MedianovaGenerator(output_root=tmp_path, seed=42)
        derby_date = date(2026, 3, 4)  # ElClasico x10
        count = gen.generate_day(derby_date)
        assert 400_000 <= count <= 600_000, f"Derby day volume: {count}"


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


def _minute_in_range(timestamp: str, start_min: int, end_min: int) -> bool:
    """Check if timestamp minute is within [start_min, end_min)."""
    # Parse minute from ISO format: ...T19:25:30Z
    parts = timestamp.split("T")[1].split(":")
    minute = int(parts[1])
    return start_min <= minute < end_min
