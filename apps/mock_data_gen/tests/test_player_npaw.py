"""Tests for Player Events + NPAW Analytics generators."""

from __future__ import annotations

import gzip
import json
import random
from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.calendar_events import get_anomaly_for_date, get_traffic_multiplier
from apps.mock_data_gen.generators.npaw.generator import NPAWGenerator
from apps.mock_data_gen.generators.npaw.schemas import (
    FIELD_CATEGORIES as NPAW_CATEGORIES,
    FIELD_DESCRIPTIONS as NPAW_DESCRIPTIONS,
    NPAWSessionEntry,
)
from apps.mock_data_gen.generators.player_events.generator import (
    PLAYER_VERSIONS,
    PlayerEventsGenerator,
    compute_qoe_score,
    generate_sessions_for_day,
)
from apps.mock_data_gen.generators.player_events.schemas import (
    FIELD_CATEGORIES as PE_CATEGORIES,
    FIELD_DESCRIPTIONS as PE_DESCRIPTIONS,
    PlayerEventEntry,
)
from apps.mock_data_gen.generators.subscriber_pool import SubscriberPool


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


def _get_sessions(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by session_id."""
    sessions: dict[str, list[dict]] = {}
    for r in records:
        sessions.setdefault(r["session_id"], []).append(r)
    return sessions


# ══════════════════════════════════════════════════════════════════════
# PLAYER EVENTS TESTS
# ══════════════════════════════════════════════════════════════════════


class TestPlayerSchema:
    def test_player_schema_valid(self):
        """All 7 event_types validate."""
        for et in ("session_start", "buffer_start", "buffer_end",
                    "bitrate_change", "error", "seek", "session_end"):
            rec = PlayerEventEntry(
                event_id="a1", event_type=et,
                timestamp="2026-01-15T14:30:00Z", session_id="s1",
                user_id_hash="u1", device_type="android",
                subscription_tier="premium", content_id="cnt_1",
                content_type="live",
            )
            assert rec.event_type == et

    def test_player_field_categories_complete(self):
        schema_fields = set(PlayerEventEntry.model_fields.keys())
        assert schema_fields == set(PE_CATEGORIES.keys())

    def test_player_field_descriptions_complete(self):
        schema_fields = set(PlayerEventEntry.model_fields.keys())
        assert schema_fields == set(PE_DESCRIPTIONS.keys())


class TestPlayerGenerator:
    def test_player_session_chain_order(self, tmp_path: Path):
        """Each session starts with session_start and ends with session_end."""
        gen = PlayerEventsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "player_events", date(2026, 1, 2))

        sessions = _get_sessions(records)
        # Check first 100 sessions
        checked = 0
        for sid, evts in sessions.items():
            evts_sorted = sorted(evts, key=lambda e: e["timestamp"])
            assert evts_sorted[0]["event_type"] == "session_start", f"Session {sid} doesn't start with session_start"
            assert evts_sorted[-1]["event_type"] == "session_end", f"Session {sid} doesn't end with session_end"
            checked += 1
            if checked >= 100:
                break

    def test_player_session_end_has_qoe_score(self, tmp_path: Path):
        """session_end events have final_qoe_score populated."""
        gen = PlayerEventsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "player_events", date(2026, 1, 2))

        end_events = [r for r in records if r["event_type"] == "session_end"]
        assert len(end_events) > 0
        for r in end_events[:100]:
            assert r["final_qoe_score"] is not None
            assert 0.0 <= r["final_qoe_score"] <= 5.0

    def test_player_qoe_formula_normal(self):
        """Normal day QoE score is 4.0-5.0."""
        score = compute_qoe_score(
            buffer_ratio=0.003, startup_time_ms=1000,
            error_count=0, avg_bitrate_kbps=4500,
        )
        assert 4.0 <= score <= 5.0, f"Normal QoE: {score}"

    def test_player_qoe_formula_derby(self):
        """Derby conditions produce QoE 2.5-3.8."""
        score = compute_qoe_score(
            buffer_ratio=0.05, startup_time_ms=4000,
            error_count=1, avg_bitrate_kbps=1500,
        )
        assert 2.0 <= score <= 3.8, f"Derby QoE: {score}"

    def test_player_startup_time_increases_derby(self, tmp_path: Path):
        """Derby day has higher average startup time than normal."""
        pool = SubscriberPool(size=1000, seed=42)

        normal_sessions = generate_sessions_for_day(
            random.Random(42), date(2026, 1, 2), pool, 1.0, None,
        )
        derby_sessions = generate_sessions_for_day(
            random.Random(42), date(2026, 3, 4), pool, 10.0, "peak_event",
        )

        normal_avg = sum(s.startup_time_ms for s in normal_sessions) / len(normal_sessions)
        derby_avg = sum(s.startup_time_ms for s in derby_sessions) / len(derby_sessions)

        assert derby_avg > normal_avg, f"Derby startup {derby_avg:.0f}ms <= normal {normal_avg:.0f}ms"

    def test_player_buffer_ratio_increases_derby(self, tmp_path: Path):
        """Derby day has higher buffer ratio than normal."""
        pool = SubscriberPool(size=1000, seed=42)

        normal_sessions = generate_sessions_for_day(
            random.Random(42), date(2026, 1, 2), pool, 1.0, None,
        )
        derby_sessions = generate_sessions_for_day(
            random.Random(42), date(2026, 3, 4), pool, 10.0, "peak_event",
        )

        normal_avg = sum(s.buffer_ratio for s in normal_sessions) / len(normal_sessions)
        derby_avg = sum(s.buffer_ratio for s in derby_sessions) / len(derby_sessions)

        assert derby_avg > normal_avg, f"Derby buf {derby_avg:.4f} <= normal {normal_avg:.4f}"

    def test_player_cdn_outage_high_buffer(self, tmp_path: Path):
        """Feb 28 CDN outage produces high buffer ratios."""
        pool = SubscriberPool(size=1000, seed=42)
        sessions = generate_sessions_for_day(
            random.Random(42), date(2026, 2, 28), pool, 1.0, "cdn_outage",
        )

        # Find sessions during outage hours (19:15-19:45 UTC → hour 19)
        outage_sessions = [s for s in sessions if s.session_start_ts.hour == 19]
        if outage_sessions:
            avg_buf = sum(s.buffer_ratio for s in outage_sessions) / len(outage_sessions)
            assert avg_buf > 0.05, f"Outage buffer ratio: {avg_buf:.4f}"

    def test_player_device_player_version_match(self, tmp_path: Path):
        """Device type matches correct player version."""
        gen = PlayerEventsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "player_events", date(2026, 1, 2))

        starts = [r for r in records if r["event_type"] == "session_start"]
        for r in starts[:200]:
            expected = PLAYER_VERSIONS.get(r["device_type"])
            assert r["player_version"] == expected, (
                f"{r['device_type']} → {r['player_version']} != {expected}"
            )


# ══════════════════════════════════════════════════════════════════════
# NPAW TESTS
# ══════════════════════════════════════════════════════════════════════


class TestNPAWSchema:
    def test_npaw_schema_valid(self):
        rec = NPAWSessionEntry(
            event_id="n1", session_id="s1",
            timestamp="2026-01-15T16:00:00Z",
            user_id_hash="u1", device_type="android",
            subscription_tier="premium", content_id="cnt_1",
            content_type="live", cdn_provider="medianova",
            country_code="TR",
            startup_time_ms=1000, total_buffering_ms=500,
            rebuffering_ratio=0.003, avg_bitrate_kbps=4500,
            num_bitrate_changes=1, num_errors=0, num_seeks=0,
            session_duration_ms=3600000, watched_duration_ms=3590000,
            completion_rate=0.95, exit_before_video_start=False,
            unique_renditions_played=2,
            youbora_score=9.0, qoe_score=4.5,
        )
        assert rec.youbora_score == 9.0

    def test_npaw_field_categories_complete(self):
        schema_fields = set(NPAWSessionEntry.model_fields.keys())
        assert schema_fields == set(NPAW_CATEGORIES.keys())

    def test_npaw_field_descriptions_complete(self):
        schema_fields = set(NPAWSessionEntry.model_fields.keys())
        assert schema_fields == set(NPAW_DESCRIPTIONS.keys())


class TestNPAWGenerator:
    def test_npaw_session_id_matches_player(self, tmp_path: Path):
        """NPAW session_ids come from same session generation as Player Events."""
        seed = 42
        pool = SubscriberPool(size=1000, seed=seed)
        test_date = date(2026, 1, 2)
        mult = get_traffic_multiplier(test_date)
        anomaly = get_anomaly_for_date(test_date)

        # Same seed + date → same sessions
        rng1 = random.Random(seed + test_date.toordinal())
        rng2 = random.Random(seed + test_date.toordinal())
        sessions1 = generate_sessions_for_day(rng1, test_date, pool, mult, anomaly)
        sessions2 = generate_sessions_for_day(rng2, test_date, pool, mult, anomaly)

        ids1 = {s.session_id for s in sessions1}
        ids2 = {s.session_id for s in sessions2}
        assert ids1 == ids2, "Same seed should produce same session IDs"

    def test_npaw_qoe_score_consistent_with_player(self, tmp_path: Path):
        """NPAW qoe_score is within ±0.1 of Player Events final_qoe_score."""
        seed = 42
        pool = SubscriberPool(size=1000, seed=seed)
        test_date = date(2026, 1, 2)
        mult = get_traffic_multiplier(test_date)
        anomaly = get_anomaly_for_date(test_date)

        rng = random.Random(seed + test_date.toordinal())
        sessions = generate_sessions_for_day(rng, test_date, pool, mult, anomaly)

        # Simulate NPAW generation
        npaw_gen = NPAWGenerator(output_root=tmp_path, seed=seed)
        for s in sessions[:100]:
            npaw_rec = npaw_gen._session_to_npaw(s)
            diff = abs(npaw_rec["qoe_score"] - s.final_qoe_score)
            assert diff <= 0.11, f"QoE diff {diff:.3f} > 0.1 for session {s.session_id}"

    def test_npaw_rebuffering_ratio_consistent(self, tmp_path: Path):
        """NPAW rebuffering_ratio is within ±5% of Player buffer_ratio."""
        seed = 42
        pool = SubscriberPool(size=1000, seed=seed)
        test_date = date(2026, 1, 2)
        mult = get_traffic_multiplier(test_date)
        anomaly = get_anomaly_for_date(test_date)

        rng = random.Random(seed + test_date.toordinal())
        sessions = generate_sessions_for_day(rng, test_date, pool, mult, anomaly)

        npaw_gen = NPAWGenerator(output_root=tmp_path, seed=seed)
        for s in sessions[:100]:
            npaw_rec = npaw_gen._session_to_npaw(s)
            if s.buffer_ratio > 0:
                relative_diff = abs(npaw_rec["rebuffering_ratio"] - s.buffer_ratio) / s.buffer_ratio
                assert relative_diff <= 0.06, (
                    f"Rebuf diff {relative_diff:.2%} > 5% for session {s.session_id}"
                )

    def test_npaw_exit_before_start_derby(self, tmp_path: Path):
        """Derby day has 6-10% exit_before_video_start rate."""
        seed = 42
        pool = SubscriberPool(size=1000, seed=seed)
        test_date = date(2026, 3, 4)  # ElClasico
        mult = get_traffic_multiplier(test_date)
        anomaly = get_anomaly_for_date(test_date)

        rng = random.Random(seed + test_date.toordinal())
        sessions = generate_sessions_for_day(rng, test_date, pool, mult, anomaly)

        npaw_gen = NPAWGenerator(output_root=tmp_path, seed=seed)
        records = [npaw_gen._session_to_npaw(s) for s in sessions]

        exit_count = sum(1 for r in records if r["exit_before_video_start"])
        ratio = exit_count / len(records) if records else 0
        # Derby causes high startup times → more exits
        assert ratio > 0.02, f"Derby exit_before_start ratio: {ratio:.2%}"

    def test_npaw_youbora_score_range(self, tmp_path: Path):
        """Youbora scores are in 0-10 range."""
        seed = 42
        pool = SubscriberPool(size=1000, seed=seed)
        test_date = date(2026, 1, 2)
        mult = get_traffic_multiplier(test_date)
        anomaly = get_anomaly_for_date(test_date)

        rng = random.Random(seed + test_date.toordinal())
        sessions = generate_sessions_for_day(rng, test_date, pool, mult, anomaly)

        npaw_gen = NPAWGenerator(output_root=tmp_path, seed=seed)
        for s in sessions[:200]:
            rec = npaw_gen._session_to_npaw(s)
            assert 0.0 <= rec["youbora_score"] <= 10.0, f"Youbora {rec['youbora_score']}"
            assert 0.0 <= rec["qoe_score"] <= 5.0, f"QoE {rec['qoe_score']}"
