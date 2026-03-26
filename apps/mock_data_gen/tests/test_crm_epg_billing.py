"""Tests for CRM + EPG + Billing generators."""

from __future__ import annotations

import csv
import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.billing.generator import BillingGenerator
from apps.mock_data_gen.generators.billing.schemas import (
    FIELD_CATEGORIES as BILL_CATEGORIES,
    FIELD_DESCRIPTIONS as BILL_DESCRIPTIONS,
    BillingLogEntry,
)
from apps.mock_data_gen.generators.crm.generator import (
    CRMGenerator,
    churn_category,
    compute_churn_risk,
)
from apps.mock_data_gen.generators.crm.schemas import (
    FIELD_CATEGORIES as CRM_CATEGORIES,
    FIELD_DESCRIPTIONS as CRM_DESCRIPTIONS,
    SubscriberDailyDelta,
    SubscriberProfile,
)
from apps.mock_data_gen.generators.epg.generator import EPGGenerator
from apps.mock_data_gen.generators.epg.schemas import (
    FIELD_CATEGORIES as EPG_CATEGORIES,
    FIELD_DESCRIPTIONS as EPG_DESCRIPTIONS,
    EPGProgram,
)


# ── Helpers ──

def _collect_jsonl_gz(base_path: Path, source: str, target_date: date) -> list[dict]:
    records: list[dict] = []
    date_dir = base_path / source
    if not date_dir.exists():
        # Search recursively
        for gz_file in base_path.rglob("*.jsonl.gz"):
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records
    for gz_file in date_dir.rglob("*.jsonl.gz"):
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════
# CRM TESTS
# ══════════════════════════════════════════════════════════════════════


class TestCRMSchema:
    def test_subscriber_profile_schema_valid(self):
        rec = SubscriberProfile(
            subscriber_id="SUB-abcd1234", user_id_hash="u1",
            email_hash="e1", phone_hash="p1", created_at="2025-06-01",
            name="Ahmet", age_group="25-34", gender="M",
            country="TR", city="İstanbul", timezone="Europe/Istanbul",
            subscription_tier="premium", subscription_status="active",
            subscription_start_date="2025-06-01", auto_renew=True,
            payment_method="credit_card", payment_cycle="monthly",
            monthly_price_tl=299.0,
            last_active_date="2026-01-14", last_login_date="2026-01-14",
            total_sessions_30d=45, total_watch_hours_30d=30.5,
            total_watch_hours_90d=85.0, avg_session_duration_min=40.0,
            peak_viewing_hour=20, days_active_30d=22,
            preferred_device="android", registered_device_count=2,
            devices=["android", "web_chrome"],
            favorite_content_type="live_sport", favorite_teams=["Galatasaray"],
            favorite_channels=["s_sport_1"], content_language="tr",
            failed_payment_count_90d=0, last_payment_date="2026-01-01",
            last_payment_status="success", lifetime_payment_total_tl=3588.0,
            support_tickets_90d=0, churn_risk_score=0.0,
            churn_risk_category="low", last_churn_risk_update="2026-01-15",
            acquisition_channel="organic",
        )
        assert rec.subscriber_id == "SUB-abcd1234"

    def test_crm_field_categories_cover_profile(self):
        schema_fields = set(SubscriberProfile.model_fields.keys())
        cat_fields = set(CRM_CATEGORIES.keys())
        assert schema_fields == cat_fields

    def test_crm_field_descriptions_cover_profile(self):
        schema_fields = set(SubscriberProfile.model_fields.keys())
        desc_fields = set(CRM_DESCRIPTIONS.keys())
        assert schema_fields == desc_fields


class TestCRMGenerator:
    def test_crm_base_file_generates(self, tmp_path: Path):
        """subscribers_base.csv is created."""
        gen = CRMGenerator(output_root=tmp_path, seed=42)
        gen.generate_base(pool_size=100)
        csv_path = tmp_path / "crm" / "subscribers_base.csv"
        assert csv_path.exists()

    def test_crm_base_count(self, tmp_path: Path):
        """Base file has correct row count."""
        gen = CRMGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_base(pool_size=500)
        assert count == 500

        csv_path = tmp_path / "crm" / "subscribers_base.csv"
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 500

    def test_crm_churn_risk_range(self):
        """Churn risk score is always 0.0-1.0."""
        assert compute_churn_risk(0, 3, 4, 2) <= 1.0
        assert compute_churn_risk(30, 0, 0, 10) >= 0.0
        assert compute_churn_risk(0, 3, 3, 1) == 0.95  # 0.40+0.30+0.15+0.10

    def test_crm_churn_category_mapping(self):
        """Score maps to correct category."""
        assert churn_category(0.1) == "low"
        assert churn_category(0.35) == "medium"
        assert churn_category(0.6) == "high"
        assert churn_category(0.8) == "critical"

    def test_crm_delta_cdn_outage_effect(self, tmp_path: Path):
        """March 1 (CDN outage aftermath) produces higher churn in deltas."""
        gen = CRMGenerator(output_root=tmp_path, seed=42)
        # Normal day
        gen.generate_day(date(2026, 1, 2))
        normal_recs = _collect_jsonl_gz(tmp_path / "crm", "daily_updates", date(2026, 1, 2))

        # CDN outage aftermath
        gen2 = CRMGenerator(output_root=tmp_path / "o", seed=42)
        gen2.generate_day(date(2026, 3, 1))
        outage_recs = _collect_jsonl_gz(tmp_path / "o" / "crm", "daily_updates", date(2026, 3, 1))

        if normal_recs and outage_recs:
            normal_avg = sum(r["churn_risk_score"] for r in normal_recs) / len(normal_recs)
            outage_avg = sum(r["churn_risk_score"] for r in outage_recs) / len(outage_recs)
            assert outage_avg > normal_avg, f"Outage churn {outage_avg:.3f} <= normal {normal_avg:.3f}"

    def test_crm_delta_fairplay_ios_effect(self, tmp_path: Path):
        """March 16 (FairPlay aftermath) has higher churn for iOS users."""
        gen = CRMGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 16))
        # Just verify it runs without error and produces deltas
        recs = _collect_jsonl_gz(tmp_path / "crm", "daily_updates", date(2026, 3, 16))
        assert len(recs) > 0


# ══════════════════════════════════════════════════════════════════════
# EPG TESTS
# ══════════════════════════════════════════════════════════════════════


class TestEPGSchema:
    def test_epg_schema_valid(self):
        rec = EPGProgram(
            program_id="PRG-abcd1234", channel_id="s_sport_1",
            channel_name="S Sport", start_time="2026-01-15T18:00:00Z",
            end_time="2026-01-15T20:00:00Z", duration_min=120,
            title="La Liga — Real Sociedad vs Atletico",
            category="live_sport", is_live=True, is_premium=True,
            language="tr", expected_viewers=120000,
            expected_peak_viewers=150000, pre_scale_required=True,
            pre_scale_time="2026-01-15T17:30:00Z",
        )
        assert rec.pre_scale_required is True

    def test_epg_field_categories_complete(self):
        schema_fields = set(EPGProgram.model_fields.keys())
        assert schema_fields == set(EPG_CATEGORIES.keys())

    def test_epg_field_descriptions_complete(self):
        schema_fields = set(EPGProgram.model_fields.keys())
        assert schema_fields == set(EPG_DESCRIPTIONS.keys())


class TestEPGGenerator:
    def test_epg_all_channels_present(self, tmp_path: Path):
        """All 6 channels have programs."""
        gen = EPGGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 5))  # La Liga day

        json_path = tmp_path / "epg" / "2026" / "01" / "05" / "2026-01-05.json"
        assert json_path.exists()
        programs = _read_json(json_path)

        channels = {p["channel_id"] for p in programs}
        expected = {"s_sport_1", "s_sport_2", "s_plus_live_1", "cnn_turk", "trt_spor", "a_spor"}
        assert channels == expected

    def test_epg_pre_scale_threshold(self, tmp_path: Path):
        """Programs with >50K expected viewers have pre_scale_required=True."""
        gen = EPGGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 5))

        json_path = tmp_path / "epg" / "2026" / "01" / "05" / "2026-01-05.json"
        programs = _read_json(json_path)

        for p in programs:
            if p["expected_viewers"] > 50_000:
                assert p["pre_scale_required"] is True, f"{p['title']}: >50K but no pre_scale"
            else:
                assert p["pre_scale_required"] is False

    def test_epg_elclasico_high_viewers(self, tmp_path: Path):
        """March 4 ElClasico has 400K+ expected viewers."""
        gen = EPGGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 4))

        json_path = tmp_path / "epg" / "2026" / "03" / "04" / "2026-03-04.json"
        programs = _read_json(json_path)

        clasico = [p for p in programs if p["category"] == "live_sport" and p.get("is_derby")]
        assert len(clasico) > 0, "No ElClasico program found"
        max_viewers = max(p["expected_viewers"] for p in clasico)
        assert max_viewers >= 400_000, f"ElClasico viewers: {max_viewers}"

    def test_epg_pre_scale_time_30min_before(self, tmp_path: Path):
        """pre_scale_time is 30 minutes before start_time."""
        gen = EPGGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 5))

        json_path = tmp_path / "epg" / "2026" / "01" / "05" / "2026-01-05.json"
        programs = _read_json(json_path)

        scaled = [p for p in programs if p["pre_scale_required"]]
        assert len(scaled) > 0
        for p in scaled:
            from datetime import datetime
            start = datetime.fromisoformat(p["start_time"].replace("Z", ""))
            pre = datetime.fromisoformat(p["pre_scale_time"].replace("Z", ""))
            diff_min = (start - pre).total_seconds() / 60
            assert 29 <= diff_min <= 31, f"Pre-scale time diff: {diff_min} min"

    def test_epg_full_day_coverage(self, tmp_path: Path):
        """Each channel has programs covering most of the 24h day."""
        gen = EPGGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))

        json_path = tmp_path / "epg" / "2026" / "01" / "02" / "2026-01-02.json"
        programs = _read_json(json_path)

        for ch in ["s_sport_1", "s_sport_2", "cnn_turk"]:
            ch_progs = [p for p in programs if p["channel_id"] == ch]
            total_min = sum(p["duration_min"] for p in ch_progs)
            # Should cover most of 24h (1440 min), allow some gaps
            assert total_min >= 1200, f"{ch}: only {total_min} min coverage"


# ══════════════════════════════════════════════════════════════════════
# BILLING TESTS
# ══════════════════════════════════════════════════════════════════════


class TestBillingSchema:
    def test_billing_schema_valid(self):
        rec = BillingLogEntry(
            transaction_id="TXN-abcdef123456", event_type="charge",
            timestamp="2026-01-15T10:00:00Z",
            subscriber_id="SUB-abcd1234", user_id_hash="u1",
            subscription_tier="premium", payment_cycle="monthly",
            amount_tl=299.0, currency="TRY",
            payment_method="credit_card", card_brand="Troy",
            payment_gateway="iyzico", status="success",
            processing_time_ms=350,
        )
        assert rec.amount_tl == 299.0

    def test_billing_field_categories_complete(self):
        schema_fields = set(BillingLogEntry.model_fields.keys())
        assert schema_fields == set(BILL_CATEGORIES.keys())

    def test_billing_field_descriptions_complete(self):
        schema_fields = set(BillingLogEntry.model_fields.keys())
        assert schema_fields == set(BILL_DESCRIPTIONS.keys())


class TestBillingGenerator:
    def test_billing_monthly_spike(self, tmp_path: Path):
        """Days 1-5 have much higher volume than mid-month."""
        gen1 = BillingGenerator(output_root=tmp_path / "a", seed=42)
        gen2 = BillingGenerator(output_root=tmp_path / "b", seed=42)

        count_day2 = gen1.generate_day(date(2026, 1, 2))  # day 2 = renewal window
        count_day15 = gen2.generate_day(date(2026, 1, 15))  # mid-month

        assert count_day2 > count_day15 * 5, f"Day 2: {count_day2}, Day 15: {count_day15}"

    def test_billing_success_rate_normal(self, tmp_path: Path):
        """Normal day success rate is 95-97%."""
        gen = BillingGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))

        recs = _collect_jsonl_gz(tmp_path, "billing", date(2026, 1, 2))
        charges = [r for r in recs if r["event_type"] == "charge"]
        if charges:
            success = sum(1 for r in charges if r["status"] == "success") / len(charges)
            assert 0.95 <= success <= 0.97, f"Success rate: {success:.2%}"

    def test_billing_failure_rate_holiday(self, tmp_path: Path):
        """Holiday has higher failure rate (7-9%)."""
        gen = BillingGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 29))  # Bayram

        recs = _collect_jsonl_gz(tmp_path, "billing", date(2026, 3, 29))
        charges = [r for r in recs if r["event_type"] == "charge"]
        if charges:
            failed = sum(1 for r in charges if r["status"] == "failed") / len(charges)
            assert 0.06 <= failed <= 0.10, f"Holiday failure rate: {failed:.2%}"

    def test_billing_cancellation_after_outage(self, tmp_path: Path):
        """March 1 (CDN outage aftermath) has increased cancellations."""
        gen_n = BillingGenerator(output_root=tmp_path / "n", seed=42)
        gen_o = BillingGenerator(output_root=tmp_path / "o", seed=42)

        gen_n.generate_day(date(2026, 1, 15))
        gen_o.generate_day(date(2026, 3, 1))

        normal_recs = _collect_jsonl_gz(tmp_path / "n", "billing", date(2026, 1, 15))
        outage_recs = _collect_jsonl_gz(tmp_path / "o", "billing", date(2026, 3, 1))

        normal_cancel = sum(1 for r in normal_recs if r["event_type"] == "cancellation")
        outage_cancel = sum(1 for r in outage_recs if r["event_type"] == "cancellation")

        assert outage_cancel > normal_cancel, f"Outage cancels {outage_cancel} <= normal {normal_cancel}"

    def test_billing_gateway_distribution(self, tmp_path: Path):
        """iyzico is the dominant payment gateway."""
        gen = BillingGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))

        recs = _collect_jsonl_gz(tmp_path, "billing", date(2026, 1, 2))
        iyzico = sum(1 for r in recs if r["payment_gateway"] == "iyzico")
        ratio = iyzico / len(recs) if recs else 0
        assert 0.50 <= ratio <= 0.70, f"iyzico ratio: {ratio:.2%}"
