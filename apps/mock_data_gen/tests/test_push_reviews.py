"""Tests for Push Notifications + App Reviews generators."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from apps.mock_data_gen.generators.app_reviews.generator import AppReviewsGenerator
from apps.mock_data_gen.generators.app_reviews.schemas import (
    FIELD_CATEGORIES as REV_CATEGORIES,
    FIELD_DESCRIPTIONS as REV_DESCRIPTIONS,
    AppReviewEntry,
)
from apps.mock_data_gen.generators.push_notifications.generator import PushNotificationsGenerator
from apps.mock_data_gen.generators.push_notifications.schemas import (
    FIELD_CATEGORIES as PUSH_CATEGORIES,
    FIELD_DESCRIPTIONS as PUSH_DESCRIPTIONS,
    PushNotificationEntry,
)


# ── Helpers ──

def _collect_jsonl_gz(base_path: Path, source: str, target_date: date) -> list[dict]:
    records: list[dict] = []
    src_dir = base_path / source
    if not src_dir.exists():
        return records
    for gz_file in src_dir.rglob("*.jsonl.gz"):
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════
# PUSH NOTIFICATIONS TESTS
# ══════════════════════════════════════════════════════════════════════


class TestPushSchema:
    def test_push_schema_valid(self):
        rec = PushNotificationEntry(
            notification_id="NTF-abcdef123456",
            timestamp="2026-01-15T18:30:00Z",
            subscriber_id="SUB-abcd1234", user_id_hash="u1",
            subscription_tier="premium", device_token_hash="t1",
            platform="android",
            notification_type="match_reminder",
            title="Maç Başlıyor!", body="La Liga maçı 30 dakika sonra",
        )
        assert rec.notification_type == "match_reminder"

    def test_push_field_categories_complete(self):
        schema_fields = set(PushNotificationEntry.model_fields.keys())
        assert schema_fields == set(PUSH_CATEGORIES.keys())

    def test_push_field_descriptions_complete(self):
        schema_fields = set(PushNotificationEntry.model_fields.keys())
        assert schema_fields == set(PUSH_DESCRIPTIONS.keys())


class TestPushGenerator:
    def test_push_match_reminder_30min_before(self, tmp_path: Path):
        """Match reminders are sent ~30 min before match start."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 5))  # La Liga day
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 1, 5))

        reminders = [r for r in records if r["notification_type"] == "match_reminder"]
        assert len(reminders) > 0
        # Reminders should be before match_starting
        starters = [r for r in records if r["notification_type"] == "match_starting"]
        if reminders and starters:
            earliest_reminder = min(r["timestamp"] for r in reminders)
            earliest_start = min(r["timestamp"] for r in starters)
            assert earliest_reminder < earliest_start

    def test_push_system_alert_cdn_outage(self, tmp_path: Path):
        """Feb 28 CDN outage produces system_alert notifications."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 2, 28))

        alerts = [r for r in records if r["notification_type"] == "system_alert"]
        assert len(alerts) > 0, "No system_alert on CDN outage day"

    def test_push_system_alert_ios_only_fairplay(self, tmp_path: Path):
        """March 15 FairPlay alerts go only to iOS platform."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 3, 15))

        alerts = [r for r in records if r["notification_type"] == "system_alert"]
        assert len(alerts) > 0
        platforms = {r["platform"] for r in alerts}
        assert "android" not in platforms, "Android should not get FairPlay alert"

    def test_push_service_restored_after_alert(self, tmp_path: Path):
        """service_restored comes ~32min after system_alert."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 2, 28))

        alerts = [r for r in records if r["notification_type"] == "system_alert"]
        restored = [r for r in records if r["notification_type"] == "service_restored"]
        assert len(restored) > 0, "No service_restored after alert"

        if alerts and restored:
            first_alert = min(r["timestamp"] for r in alerts)
            first_restore = min(r["timestamp"] for r in restored)
            assert first_restore > first_alert

    def test_push_open_rate_system_alert(self, tmp_path: Path):
        """system_alert open rate is 55-65%."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 2, 28))

        alerts = [r for r in records if r["notification_type"] == "system_alert" and r["delivered"]]
        if alerts:
            opened = sum(1 for r in alerts if r["opened"]) / len(alerts)
            assert 0.50 <= opened <= 0.70, f"Alert open rate: {opened:.2%}"

    def test_push_open_rate_promotional(self, tmp_path: Path):
        """Promotional open rate is 10-15%."""
        # Tuesday is promo day
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 6))  # Tuesday
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 1, 6))

        promos = [r for r in records if r["notification_type"] == "promotional" and r["delivered"]]
        if promos:
            opened = sum(1 for r in promos if r["opened"]) / len(promos)
            assert 0.08 <= opened <= 0.18, f"Promo open rate: {opened:.2%}"

    def test_push_delivery_failure_normal(self, tmp_path: Path):
        """Normal day delivery failure rate is 1-2%."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 2))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 1, 2))

        if records:
            failed = sum(1 for r in records if not r["delivered"]) / len(records)
            assert 0.005 <= failed <= 0.03, f"Delivery failure: {failed:.2%}"

    def test_push_turkish_title_body(self, tmp_path: Path):
        """Push notifications contain Turkish characters."""
        gen = PushNotificationsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 1, 5))
        records = _collect_jsonl_gz(tmp_path, "push_notifications", date(2026, 1, 5))

        # Check for Turkish chars in some records
        turkish_chars = set("çğıöşüÇĞİÖŞÜ")
        has_turkish = False
        for r in records[:200]:
            if any(c in turkish_chars for c in r["title"] + r["body"]):
                has_turkish = True
                break
        assert has_turkish, "No Turkish characters found in notifications"


# ══════════════════════════════════════════════════════════════════════
# APP REVIEWS TESTS
# ══════════════════════════════════════════════════════════════════════


class TestReviewsSchema:
    def test_reviews_schema_valid(self):
        rec = AppReviewEntry(
            review_id="REV-abcdef123456", platform="android",
            timestamp="2026-01-15T14:30:00Z", app_version="4.2.1",
            device_model="Samsung Galaxy S24", os_version="Android 14",
            country="TR", language="tr",
            rating=5, body="Harika uygulama",
            sentiment="positive", category="content",
            topics=["content", "live_sport"], language_detected="tr",
        )
        assert rec.rating == 5

    def test_reviews_field_categories_complete(self):
        schema_fields = set(AppReviewEntry.model_fields.keys())
        assert schema_fields == set(REV_CATEGORIES.keys())

    def test_reviews_field_descriptions_complete(self):
        schema_fields = set(AppReviewEntry.model_fields.keys())
        assert schema_fields == set(REV_DESCRIPTIONS.keys())


class TestReviewsGenerator:
    def test_reviews_normal_day_volume(self, tmp_path: Path):
        """Normal day produces 15-30 reviews."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 1, 2))
        assert 15 <= count <= 30, f"Normal day reviews: {count}"

    def test_reviews_cdn_outage_volume(self, tmp_path: Path):
        """CDN outage day produces 250+ reviews."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 2, 28))
        assert count >= 250, f"CDN outage reviews: {count}"

    def test_reviews_elclasico_volume(self, tmp_path: Path):
        """ElClasico day produces 400+ reviews."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        count = gen.generate_day(date(2026, 3, 4))
        assert count >= 400, f"ElClasico reviews: {count}"

    def test_reviews_fairplay_ios_drm_category(self, tmp_path: Path):
        """March 15 iOS reviews have DRM category dominant."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))

        json_path = tmp_path / "app_reviews" / "2026" / "03" / "2026-03-15.json"
        reviews = _read_json(json_path)

        ios_negative = [r for r in reviews if r["platform"] == "ios" and r["rating"] <= 2]
        if ios_negative:
            drm_count = sum(1 for r in ios_negative if r["category"] == "drm")
            ratio = drm_count / len(ios_negative)
            assert ratio > 0.50, f"iOS DRM ratio on FairPlay day: {ratio:.2%}"

    def test_reviews_rating_negative_on_outage(self, tmp_path: Path):
        """CDN outage day average rating < 2.5."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))

        json_path = tmp_path / "app_reviews" / "2026" / "02" / "2026-02-28.json"
        reviews = _read_json(json_path)

        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
        assert avg_rating < 2.5, f"CDN outage avg rating: {avg_rating:.2f}"

    def test_reviews_android_not_affected_fairplay(self, tmp_path: Path):
        """Android reviews on March 15 are not DRM-dominated."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 3, 15))

        json_path = tmp_path / "app_reviews" / "2026" / "03" / "2026-03-15.json"
        reviews = _read_json(json_path)

        android_recs = [r for r in reviews if r["platform"] == "android"]
        if android_recs:
            drm_count = sum(1 for r in android_recs if r["category"] == "drm")
            ratio = drm_count / len(android_recs)
            # Android shouldn't have high DRM ratio
            assert ratio < 0.30, f"Android DRM ratio on FairPlay day: {ratio:.2%}"

    def test_reviews_developer_response_rate(self, tmp_path: Path):
        """Negative reviews get 12-18% developer response."""
        gen = AppReviewsGenerator(output_root=tmp_path, seed=42)
        gen.generate_day(date(2026, 2, 28))  # outage = many negative

        json_path = tmp_path / "app_reviews" / "2026" / "02" / "2026-02-28.json"
        reviews = _read_json(json_path)

        negative = [r for r in reviews if r["rating"] <= 2]
        if negative:
            responded = sum(1 for r in negative if r["developer_response"]) / len(negative)
            # Outage day has 35% response rate, normal 15%
            assert 0.10 <= responded <= 0.45, f"Dev response rate: {responded:.2%}"
