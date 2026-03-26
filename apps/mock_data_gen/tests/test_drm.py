"""Tests for Widevine + FairPlay DRM generators."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.drm_fairplay.generator import FairPlayGenerator
from apps.mock_data_gen.generators.drm_fairplay.schemas import (
    FIELD_CATEGORIES as FP_CATEGORIES,
    FIELD_DESCRIPTIONS as FP_DESCRIPTIONS,
    FairPlayLogEntry,
)
from apps.mock_data_gen.generators.drm_widevine.generator import WidevineGenerator
from apps.mock_data_gen.generators.drm_widevine.schemas import (
    FIELD_CATEGORIES as WV_CATEGORIES,
    FIELD_DESCRIPTIONS as WV_DESCRIPTIONS,
    WidevineLogEntry,
)
from apps.mock_data_gen.generators.subscriber_pool import DEVICE_DISTRIBUTION, DRM_BY_DEVICE


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
# WIDEVINE TESTS
# ══════════════════════════════════════════════════════════════════════


class TestWidevineSchema:
    def test_widevine_schema_valid(self):
        """Sample Widevine record validates."""
        rec = WidevineLogEntry(
            event_id="a1", event_type="license_request",
            timestamp="2026-01-15T14:30:00Z", drm_server="drm.ssport.com.tr",
            session_id="s1", device_id_hash="d1", user_id_hash="u1",
            subscription_tier="premium",
            content_id="cnt_1234", content_type="live", channel="s_sport_1",
            device_type="android", widevine_security_level="L1",
            license_type="streaming",
            status="success", response_time_ms=100,
            country_code="TR", ip_hash="ip1",
        )
        assert rec.status == "success"
        assert rec.widevine_security_level == "L1"

    def test_widevine_field_categories_complete(self):
        schema_fields = set(WidevineLogEntry.model_fields.keys())
        assert schema_fields == set(WV_CATEGORIES.keys())

    def test_widevine_field_descriptions_complete(self):
        schema_fields = set(WidevineLogEntry.model_fields.keys())
        assert schema_fields == set(WV_DESCRIPTIONS.keys())


class TestWidevineGenerator:
    def test_widevine_only_widevine_devices(self, tmp_path: Path):
        """No iOS/Apple TV/Safari devices in Widevine logs."""
        gen = WidevineGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_widevine", date(2026, 1, 2))

        apple_devices = {"ios", "apple_tv", "web_safari"}
        device_types = {r["device_type"] for r in records}
        assert device_types.isdisjoint(apple_devices), f"Apple devices found: {device_types & apple_devices}"

    def test_widevine_security_level_l3_for_web(self, tmp_path: Path):
        """web_chrome always has L3 security level."""
        gen = WidevineGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_widevine", date(2026, 1, 2))

        chrome_recs = [r for r in records if r["device_type"] == "web_chrome"]
        assert len(chrome_recs) > 0
        for r in chrome_recs:
            assert r["widevine_security_level"] == "L3"

    def test_widevine_security_level_l1_for_android(self, tmp_path: Path):
        """Android devices have L1 as dominant security level."""
        gen = WidevineGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_widevine", date(2026, 1, 2))

        android_recs = [r for r in records if r["device_type"] == "android"]
        assert len(android_recs) > 0
        l1_count = sum(1 for r in android_recs if r["widevine_security_level"] == "L1")
        ratio = l1_count / len(android_recs)
        assert ratio > 0.50, f"Android L1 ratio: {ratio:.2%}"

    def test_widevine_success_rate_normal(self, tmp_path: Path):
        """Normal day success rate is 98-100%."""
        gen = WidevineGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_widevine", date(2026, 1, 2))

        success_count = sum(1 for r in records if r["status"] == "success")
        ratio = success_count / len(records)
        assert 0.98 <= ratio <= 1.0, f"Success ratio: {ratio:.2%}"

    def test_widevine_timeout_spike_derby(self, tmp_path: Path):
        """Derby day has increased timeout rate vs normal."""
        gen_n = WidevineGenerator(output_root=tmp_path / "n", seed=42)
        gen_d = WidevineGenerator(output_root=tmp_path / "d", seed=42)

        gen_n.generate_day(date(2026, 1, 2))
        gen_d.generate_day(date(2026, 3, 4))  # ElClasico x10

        normal_recs = _collect_records(tmp_path / "n", "drm_widevine", date(2026, 1, 2))
        derby_recs = _collect_records(tmp_path / "d", "drm_widevine", date(2026, 3, 4))

        normal_to = sum(1 for r in normal_recs if r["status"] == "timeout") / len(normal_recs)
        derby_to = sum(1 for r in derby_recs if r["status"] == "timeout") / len(derby_recs)

        assert derby_to > normal_to, f"Derby timeout {derby_to:.3%} <= normal {normal_to:.3%}"

    def test_widevine_renewal_chain(self, tmp_path: Path):
        """Sessions contain renewal events."""
        gen = WidevineGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_widevine", date(2026, 1, 2))

        renewals = [r for r in records if r["event_type"] == "license_renewal"]
        assert len(renewals) > 0, "No renewal events found"

        # Renewals should share session_id with a license_request
        renewal_sessions = {r["session_id"] for r in renewals}
        request_sessions = {r["session_id"] for r in records if r["event_type"] == "license_request"}
        assert renewal_sessions.issubset(request_sessions), "Orphan renewals found"


# ══════════════════════════════════════════════════════════════════════
# FAIRPLAY TESTS
# ══════════════════════════════════════════════════════════════════════


class TestFairPlaySchema:
    def test_fairplay_schema_valid(self):
        """Sample FairPlay record validates."""
        rec = FairPlayLogEntry(
            event_id="b1", event_type="license_request",
            timestamp="2026-01-15T14:30:00Z", drm_server="drm.ssport.com.tr",
            session_id="s2", device_id_hash="d2", user_id_hash="u2",
            subscription_tier="premium",
            content_id="cnt_5678", content_type="live", channel="s_sport_1",
            device_type="ios", device_model="iPhone 15 Pro",
            ios_version="iOS 17.2",
            certificate_status="valid", ksm_response_code=200,
            license_type="streaming",
            status="success", response_time_ms=120,
            country_code="TR", ip_hash="ip2",
        )
        assert rec.certificate_status == "valid"

    def test_fairplay_field_categories_complete(self):
        schema_fields = set(FairPlayLogEntry.model_fields.keys())
        assert schema_fields == set(FP_CATEGORIES.keys())

    def test_fairplay_field_descriptions_complete(self):
        schema_fields = set(FairPlayLogEntry.model_fields.keys())
        assert schema_fields == set(FP_DESCRIPTIONS.keys())


class TestFairPlayGenerator:
    def test_fairplay_only_apple_devices(self, tmp_path: Path):
        """No Android/Chrome/Firefox/Tizen/webOS in FairPlay logs."""
        gen = FairPlayGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_fairplay", date(2026, 1, 2))

        widevine_devices = {"android", "web_chrome", "web_firefox", "android_tv", "tizen_os", "webos"}
        device_types = {r["device_type"] for r in records}
        assert device_types.isdisjoint(widevine_devices), f"Widevine devices found: {device_types & widevine_devices}"

    def test_fairplay_cert_valid_normal_day(self, tmp_path: Path):
        """Normal day has no expired certificates."""
        gen = FairPlayGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_records(tmp_path, "drm_fairplay", date(2026, 1, 2))

        expired = [r for r in records if r["certificate_status"] == "expired"]
        assert len(expired) == 0, f"Found {len(expired)} expired certs on normal day"

    def test_fairplay_cert_expired_march15(self, tmp_path: Path):
        """March 15 10:00 UTC has 100% expired certs for ios/apple_tv."""
        gen = FairPlayGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))
        records = _collect_records(tmp_path, "drm_fairplay", date(2026, 3, 15))

        # Filter records at 10:xx UTC for ios/apple_tv
        affected_recs = [
            r for r in records
            if r["device_type"] in ("ios", "apple_tv")
            and "T10:" in r["timestamp"]
        ]

        assert len(affected_recs) > 0
        expired_count = sum(1 for r in affected_recs if r["certificate_status"] == "expired")
        assert expired_count == len(affected_recs), (
            f"Expected 100% expired at 10:xx UTC, got {expired_count}/{len(affected_recs)}"
        )

    def test_fairplay_safari_unaffected_march15(self, tmp_path: Path):
        """web_safari is NOT affected by March 15 cert expiry."""
        gen = FairPlayGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))
        records = _collect_records(tmp_path, "drm_fairplay", date(2026, 3, 15))

        safari_recs = [r for r in records if r["device_type"] == "web_safari"]
        assert len(safari_recs) > 0
        for r in safari_recs:
            assert r["certificate_status"] == "valid", "web_safari should be unaffected"

    def test_fairplay_cert_restored_after_18utc(self, tmp_path: Path):
        """March 15 after 18:00 UTC, certs are valid again."""
        gen = FairPlayGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))
        records = _collect_records(tmp_path, "drm_fairplay", date(2026, 3, 15))

        # Records at 19:xx UTC for ios/apple_tv
        restored_recs = [
            r for r in records
            if r["device_type"] in ("ios", "apple_tv")
            and "T19:" in r["timestamp"]
        ]

        assert len(restored_recs) > 0
        for r in restored_recs:
            assert r["certificate_status"] == "valid", "Cert should be restored after 18 UTC"


# ══════════════════════════════════════════════════════════════════════
# CROSS-DRM TESTS
# ══════════════════════════════════════════════════════════════════════


class TestDRMDeviceCoverage:
    def test_drm_device_coverage_complete(self):
        """Every device type maps to either Widevine or FairPlay."""
        widevine = {"android", "web_chrome", "web_firefox", "android_tv", "tizen_os", "webos"}
        fairplay = {"ios", "apple_tv", "web_safari"}

        all_devices = set(DEVICE_DISTRIBUTION.keys())
        covered = widevine | fairplay
        assert all_devices == covered, f"Uncovered devices: {all_devices - covered}"

        # Verify DRM_BY_DEVICE mapping is consistent
        for device, drm in DRM_BY_DEVICE.items():
            if drm == "widevine":
                assert device in widevine, f"{device} should be widevine"
            else:
                assert device in fairplay, f"{device} should be fairplay"
