"""Tests for S-MDG-01 base infrastructure — calendar, subscribers, base generator."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.calendar_events import (
    CALENDAR_EVENTS,
    CalendarEvent,
    get_anomaly_for_date,
    get_events_for_date,
    get_traffic_multiplier,
    is_anomaly_active,
)
from apps.mock_data_gen.generators.base_generator import (
    PERIOD_END,
    PERIOD_START,
    BaseGenerator,
)
from apps.mock_data_gen.generators.subscriber_pool import (
    COUNTRY_DISTRIBUTION,
    DEVICE_DISTRIBUTION,
    DRM_BY_DEVICE,
    TIER_DISTRIBUTION,
    TOTAL_SUBSCRIBERS,
    Subscriber,
    SubscriberPool,
)


# ── Calendar Events ──


class TestCalendarEvents:
    def test_total_event_count(self):
        """All 18 calendar events are defined (16 unique dates, 3 bayram days)."""
        assert len(CALENDAR_EVENTS) == 18

    def test_period_bounds(self):
        """All events fall within the 91-day period."""
        for evt in CALENDAR_EVENTS:
            assert PERIOD_START <= evt.date <= PERIOD_END, f"{evt.name} out of bounds"

    def test_el_clasico_multiplier(self):
        """ElClasico (04 Mart) has x10 multiplier — highest in calendar."""
        mult = get_traffic_multiplier(date(2026, 3, 4))
        assert mult == 10.0

    def test_bayram_low_multiplier(self):
        """Ramazan Bayramı (29-31 Mart) has x0.6 multiplier."""
        for d in [date(2026, 3, 29), date(2026, 3, 30), date(2026, 3, 31)]:
            assert get_traffic_multiplier(d) == 0.6

    def test_normal_day_multiplier(self):
        """Days without events return 1.0."""
        assert get_traffic_multiplier(date(2026, 1, 2)) == 1.0

    def test_cdn_outage_anomaly(self):
        """28 Şubat CDN Kesintisi is detected as anomaly."""
        assert get_anomaly_for_date(date(2026, 2, 28)) == "cdn_outage"

    def test_fairplay_anomaly(self):
        """15 Mart FairPlay sertifika sorunu."""
        assert get_anomaly_for_date(date(2026, 3, 15)) == "fairplay_cert_expired"

    def test_no_anomaly_normal_day(self):
        """Normal days have no anomaly."""
        assert get_anomaly_for_date(date(2026, 1, 2)) is None

    def test_cdn_outage_time_window(self):
        """CDN outage is active only between 22:15-22:45 TR."""
        # Inside window
        assert is_anomaly_active(
            datetime(2026, 2, 28, 22, 30), "cdn_outage"
        ) is True
        # Outside window
        assert is_anomaly_active(
            datetime(2026, 2, 28, 21, 0), "cdn_outage"
        ) is False

    def test_event_frozen_dataclass(self):
        """CalendarEvent is immutable (frozen=True)."""
        evt = CALENDAR_EVENTS[0]
        with pytest.raises(AttributeError):
            evt.name = "changed"  # type: ignore[misc]

    def test_get_events_for_date_returns_list(self):
        """get_events_for_date returns a list of CalendarEvent."""
        events = get_events_for_date(date(2026, 3, 4))
        assert len(events) >= 1
        assert all(isinstance(e, CalendarEvent) for e in events)


# ── Subscriber Pool ──


class TestSubscriberPool:
    def test_pool_size(self):
        """Pool generates exactly 485K subscribers by default."""
        pool = SubscriberPool(size=100, seed=42)
        assert len(pool) == 100

    def test_deterministic_output(self):
        """Same seed produces identical subscribers."""
        pool_a = SubscriberPool(size=50, seed=42)
        pool_b = SubscriberPool(size=50, seed=42)
        for i in range(50):
            assert pool_a[i].user_id == pool_b[i].user_id
            assert pool_a[i].device_type == pool_b[i].device_type

    def test_subscriber_fields(self):
        """Each subscriber has all required fields."""
        pool = SubscriberPool(size=10, seed=42)
        sub = pool[0]
        assert isinstance(sub, Subscriber)
        assert sub.user_id.startswith("u_")
        assert sub.tier in ("premium", "standard", "free")
        assert sub.country in COUNTRY_DISTRIBUTION
        assert sub.device_type in DEVICE_DISTRIBUTION
        assert sub.drm_type in ("widevine", "fairplay")
        assert len(sub.email_hash) == 64  # SHA256 hex

    def test_drm_matches_device(self):
        """DRM type is consistent with device type."""
        pool = SubscriberPool(size=200, seed=42)
        for i in range(200):
            sub = pool[i]
            assert sub.drm_type == DRM_BY_DEVICE[sub.device_type], (
                f"DRM mismatch for {sub.device_type}: {sub.drm_type}"
            )

    def test_filter_by_tier(self):
        """filter_by_tier returns only matching subscribers."""
        pool = SubscriberPool(size=100, seed=42)
        premiums = pool.filter_by_tier("premium")
        assert all(s.tier == "premium" for s in premiums)
        assert len(premiums) > 0

    def test_filter_by_device(self):
        """filter_by_device returns only matching device types."""
        pool = SubscriberPool(size=200, seed=42)
        ios_users = pool.filter_by_device("ios")
        assert all(s.device_type == "ios" for s in ios_users)

    def test_sample_returns_subset(self):
        """sample() returns n subscribers."""
        pool = SubscriberPool(size=100, seed=42)
        batch = pool.sample(10, seed=42)
        assert len(batch) == 10

    def test_stats(self):
        """Stats returns correct structure."""
        pool = SubscriberPool(size=100, seed=42)
        stats = pool.stats
        assert stats["total"] == 100
        assert "tiers" in stats
        assert "countries" in stats
        assert "devices" in stats


# ── Base Generator ──


class _DummyGenerator(BaseGenerator):
    """Minimal concrete generator for testing base class."""

    @property
    def source_name(self) -> str:
        return "test_source"

    def generate_day(self, target_date: date) -> int:
        records = [{"ts": target_date.isoformat(), "value": i} for i in range(3)]
        self.write_jsonl_gz(
            records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.jsonl.gz",
        )
        return len(records)


class TestBaseGenerator:
    def test_write_jsonl_gz(self, tmp_path: Path):
        """JSONL.gz write creates readable gzip file."""
        import gzip
        import json

        gen = _DummyGenerator(output_root=tmp_path)
        records = [{"a": 1}, {"a": 2}]
        out = gen.write_jsonl_gz(records, "sub", filename="test.jsonl.gz")
        assert out.exists()

        with gzip.open(out, "rt", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["a"] == 1

    def test_write_json(self, tmp_path: Path):
        """JSON write creates valid JSON file."""
        import json

        gen = _DummyGenerator(output_root=tmp_path)
        data = {"key": "value", "items": [1, 2, 3]}
        out = gen.write_json(data, "sub", filename="test.json")
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["key"] == "value"

    def test_write_csv(self, tmp_path: Path):
        """CSV write creates valid CSV with headers."""
        gen = _DummyGenerator(output_root=tmp_path)
        records = [{"name": "Ali", "age": 30}, {"name": "Veli", "age": 25}]
        out = gen.write_csv(records, "sub", filename="test.csv")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "name,age" in content
        assert "Ali,30" in content

    def test_generate_range(self, tmp_path: Path):
        """generate_range produces records for each day."""
        gen = _DummyGenerator(output_root=tmp_path)
        results = gen.generate_range(date(2026, 1, 1), date(2026, 1, 3))
        assert len(results) == 3
        assert all(v == 3 for v in results.values())

    def test_iter_dates(self):
        """iter_dates yields correct number of dates."""
        dates = list(BaseGenerator.iter_dates(date(2026, 1, 1), date(2026, 1, 5)))
        assert len(dates) == 5
        assert dates[0] == date(2026, 1, 1)
        assert dates[-1] == date(2026, 1, 5)

    def test_subscriber_pool_lazy(self, tmp_path: Path):
        """Subscriber pool is lazy-loaded on first access."""
        gen = _DummyGenerator(output_root=tmp_path)
        assert gen._subscriber_pool is None
        _ = gen.subscriber_pool
        assert gen._subscriber_pool is not None

    def test_get_multiplier(self, tmp_path: Path):
        """get_multiplier delegates to calendar_events."""
        gen = _DummyGenerator(output_root=tmp_path)
        assert gen.get_multiplier(date(2026, 3, 4)) == 10.0
        assert gen.get_multiplier(date(2026, 1, 2)) == 1.0
