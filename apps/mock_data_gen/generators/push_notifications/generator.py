"""Push Notifications generator — match reminders, system alerts, promotions.

Output: push_notifications/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
    get_events_for_date,
)

logger = structlog.get_logger(__name__)

# Open/conversion rates by notification type
ENGAGEMENT_RATES: dict[str, dict[str, float]] = {
    "match_reminder": {"open": 0.28, "conversion": 0.22},
    "match_starting": {"open": 0.42, "conversion": 0.38},
    "score_update": {"open": 0.35, "conversion": 0.18},
    "system_alert": {"open": 0.61, "conversion": 0.0},
    "service_restored": {"open": 0.55, "conversion": 0.31},
    "payment_failed": {"open": 0.48, "conversion": 0.29},
    "promotional": {"open": 0.12, "conversion": 0.08},
    "subscription_expiry": {"open": 0.52, "conversion": 0.35},
    "new_content": {"open": 0.20, "conversion": 0.15},
    "personalized": {"open": 0.25, "conversion": 0.18},
}

# Turkish notification templates
TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "match_reminder": [
        ("Maç Başlıyor!", "{teams} 30 dakika sonra başlıyor"),
        ("Maç Hatırlatması", "{competition} maçı yaklaşıyor — {teams}"),
        ("Kaçırma!", "{teams} maçı 30 dakika içinde S Sport'ta"),
    ],
    "match_starting": [
        ("Canlı Yayın", "{teams} başladı! Hemen izle"),
        ("CANLI", "{competition} — {teams} şu an canlı yayında"),
        ("Maç Başladı!", "{teams} canlı yayında, hemen katıl"),
    ],
    "score_update": [
        ("GOL!", "{teams} — {score}. dakika"),
        ("Skor Güncellemesi", "{teams} maçında gol! {score}"),
        ("GOOOL!", "{competition}: {teams} — {score}"),
    ],
    "system_alert": [
        ("Yayın Sorunu", "Bazı kanallarda yayın sorunu yaşıyoruz, ekibimiz çalışıyor"),
        ("Teknik Sorun", "Geçici bir teknik sorun yaşanıyor, en kısa sürede çözülecek"),
    ],
    "service_restored": [
        ("Yayın Normale Döndü", "Yayın hizmeti normale döndü, izlemeye devam edebilirsiniz"),
        ("Sorun Giderildi", "Teknik sorun giderildi, keyifli seyirler"),
    ],
    "payment_failed": [
        ("Ödeme Başarısız", "Abonelik ödemesi alınamadı, lütfen ödeme bilgilerinizi güncelleyin"),
        ("Ödeme Hatası", "Son ödemeniz başarısız oldu. Aboneliğinizin devamı için bilgilerinizi kontrol edin"),
    ],
    "promotional": [
        ("Özel Teklif", "3 ay %50 indirimle S Sport Plus Premium"),
        ("Fırsat!", "Yıllık abonelikte %30 indirim — sadece bu hafta"),
        ("Kampanya", "Arkadaşını getir, 1 ay ücretsiz kazan"),
    ],
    "subscription_expiry": [
        ("Aboneliğiniz Bitiyor", "Aboneliğiniz 3 gün içinde sona eriyor"),
        ("Yenileme Hatırlatması", "S Sport Plus aboneliğiniz yakında sona erecek, yenileyin"),
    ],
    "new_content": [
        ("Yeni İçerik", "Bu haftanın maç özetleri yayında"),
        ("Yeni Eklenen", "Özel röportajlar ve stüdyo analizleri eklendi"),
    ],
    "personalized": [
        ("Senin İçin", "Favori takımın bu hafta oynuyor, takvimini kontrol et"),
        ("Öneri", "Geçen hafta izlediğin {competition} yeni maçları var"),
    ],
}

FAILURE_REASONS_NORMAL = {"token_expired": 0.60, "app_uninstalled": 0.30, "network_error": 0.10}
FAILURE_REASONS_DERBY = {"rate_limited": 0.70, "token_expired": 0.20, "network_error": 0.10}

APP_VERSIONS = ["4.2.1", "4.2.0", "4.1.9"]


class PushNotificationsGenerator(BaseGenerator):
    """Generates push notification logs."""

    @property
    def source_name(self) -> str:
        return "push_notifications"

    def _pick_weighted(self, options: dict) -> str:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _make_notification(self, ts: datetime, sub, notif_type: str,
                           title: str, body: str, multiplier: float,
                           channel_id: str | None = None,
                           competition: str | None = None,
                           content_id: str | None = None) -> dict:
        platform_map = {
            "android": "android", "android_tv": "android",
            "ios": "ios", "apple_tv": "ios",
            "web_chrome": "web", "web_firefox": "web", "web_safari": "web",
            "tizen_os": "android", "webos": "android",
        }
        platform = platform_map.get(sub.device_type, "android")

        # Delivery
        is_derby = multiplier >= 2.5
        fail_rate = 0.03 if is_derby else 0.015
        delivered = self.rng.random() >= fail_rate
        failure = None
        if not delivered:
            reasons = FAILURE_REASONS_DERBY if is_derby else FAILURE_REASONS_NORMAL
            failure = self._pick_weighted(reasons)

        # Engagement
        rates = ENGAGEMENT_RATES.get(notif_type, {"open": 0.15, "conversion": 0.10})
        opened = delivered and self.rng.random() < rates["open"]
        converted = opened and rates["conversion"] > 0 and self.rng.random() < rates["conversion"]

        delivered_at = None
        opened_at = None
        latency = None
        if delivered:
            latency = self.rng.randint(50, 500) if not is_derby else self.rng.randint(200, 3000)
            delivered_at = (ts + timedelta(milliseconds=latency)).replace(tzinfo=None).isoformat() + "Z"
        if opened:
            open_delay = self.rng.randint(5, 600)  # 5s to 10min
            opened_at = (ts + timedelta(seconds=open_delay)).replace(tzinfo=None).isoformat() + "Z"

        sub_id = f"SUB-{hashlib.sha256(sub.user_id.encode()).hexdigest()[:8]}"
        token_hash = hashlib.sha256(f"token_{sub.user_id}_{sub.device_type}".encode()).hexdigest()[:32]

        campaign = None
        if notif_type in ("promotional", "personalized", "new_content"):
            campaign = f"MKT-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:8]}"

        deep_link = None
        if channel_id:
            deep_link = f"ssportplus://live/{channel_id}"
        elif content_id:
            deep_link = f"ssportplus://content/{content_id}"

        return {
            "notification_id": f"NTF-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]}",
            "campaign_id": campaign,
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "delivered_at": delivered_at,
            "opened_at": opened_at,
            "subscriber_id": sub_id,
            "user_id_hash": hashlib.sha256(sub.user_id.encode()).hexdigest()[:32],
            "subscription_tier": sub.tier,
            "device_token_hash": token_hash,
            "platform": platform,
            "app_version": self.rng.choice(APP_VERSIONS),
            "notification_type": notif_type,
            "title": title,
            "body": body,
            "deep_link": deep_link,
            "image_url": f"https://cdn.ssport.com.tr/push/{notif_type}.jpg" if self.rng.random() < 0.3 else None,
            "content_id": content_id,
            "channel_id": channel_id,
            "competition": competition,
            "delivered": delivered,
            "opened": opened,
            "delivery_latency_ms": latency,
            "failure_reason": failure,
            "ctr": round(rates["open"], 3),
            "conversion": converted,
            "conversion_content_id": content_id if converted else None,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate push notifications for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)
        events = get_events_for_date(target_date)
        pool = self.subscriber_pool
        records: list[dict] = []

        # ── Match-related notifications ──
        for evt in events:
            if not evt.competition:
                continue

            teams_str = evt.name.split(" — ")[-1] if " — " in evt.name else evt.name
            channel = list(evt.channels)[0] if evt.channels else "s_sport_1"

            # match_reminder: 30 min before, ~20K subscribers
            reminder_count = min(20_000, len(pool))
            if multiplier >= 10:
                reminder_count = min(100_000, len(pool))

            match_hour = 19  # default
            reminder_ts = datetime(
                target_date.year, target_date.month, target_date.day,
                match_hour - 1, 30, 0, tzinfo=timezone.utc,
            )
            match_ts = datetime(
                target_date.year, target_date.month, target_date.day,
                match_hour, 0, 0, tzinfo=timezone.utc,
            )

            # Reminders
            for i in range(min(reminder_count, 5000)):  # cap for perf
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                tmpl = self.rng.choice(TEMPLATES["match_reminder"])
                title, body = tmpl[0], tmpl[1].format(
                    teams=teams_str, competition=evt.competition,
                )
                records.append(self._make_notification(
                    reminder_ts, sub, "match_reminder", title, body,
                    multiplier, channel_id=channel, competition=evt.competition,
                ))

            # match_starting
            for i in range(min(reminder_count, 5000)):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                tmpl = self.rng.choice(TEMPLATES["match_starting"])
                title, body = tmpl[0], tmpl[1].format(
                    teams=teams_str, competition=evt.competition,
                )
                records.append(self._make_notification(
                    match_ts, sub, "match_starting", title, body,
                    multiplier, channel_id=channel, competition=evt.competition,
                ))

            # score_update: ~3 goals per match
            num_goals = self.rng.randint(2, 4)
            for g in range(num_goals):
                goal_min = self.rng.randint(5, 90)
                goal_ts = match_ts + timedelta(minutes=goal_min)
                for i in range(min(3000, len(pool))):
                    sub = pool[self.rng.randint(0, len(pool) - 1)]
                    tmpl = self.rng.choice(TEMPLATES["score_update"])
                    title, body = tmpl[0], tmpl[1].format(
                        teams=teams_str, competition=evt.competition,
                        score=f"{goal_min}",
                    )
                    records.append(self._make_notification(
                        goal_ts, sub, "score_update", title, body,
                        multiplier, channel_id=channel, competition=evt.competition,
                    ))

        # ── System alerts ──
        if anomaly == "cdn_outage":
            alert_ts = datetime(target_date.year, target_date.month, target_date.day,
                                19, 17, 0, tzinfo=timezone.utc)
            for i in range(min(50_000, len(pool))):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                tmpl = self.rng.choice(TEMPLATES["system_alert"])
                records.append(self._make_notification(
                    alert_ts, sub, "system_alert", tmpl[0], tmpl[1], multiplier,
                ))

            # service_restored ~32 min later
            restore_ts = alert_ts + timedelta(minutes=32)
            for i in range(min(50_000, len(pool))):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                tmpl = self.rng.choice(TEMPLATES["service_restored"])
                records.append(self._make_notification(
                    restore_ts, sub, "service_restored", tmpl[0], tmpl[1], multiplier,
                ))

        if anomaly == "fairplay_cert_expired":
            alert_ts = datetime(target_date.year, target_date.month, target_date.day,
                                9, 15, 0, tzinfo=timezone.utc)
            for i in range(min(20_000, len(pool))):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                if sub.device_type not in ("ios", "apple_tv", "web_safari"):
                    continue
                tmpl = self.rng.choice(TEMPLATES["system_alert"])
                records.append(self._make_notification(
                    alert_ts, sub, "system_alert", tmpl[0], tmpl[1], multiplier,
                ))

        # ── Payment failed (~2K/day) ──
        for i in range(2000):
            sub = pool[self.rng.randint(0, len(pool) - 1)]
            hour = self.rng.randint(8, 18)
            ts = datetime(target_date.year, target_date.month, target_date.day,
                          hour, self.rng.randint(0, 59), 0, tzinfo=timezone.utc)
            tmpl = self.rng.choice(TEMPLATES["payment_failed"])
            records.append(self._make_notification(
                ts, sub, "payment_failed", tmpl[0], tmpl[1], multiplier,
            ))

        # ── Promotional (Tue/Fri, ~5K sample for perf) ──
        if target_date.weekday() in (1, 4):  # Tuesday, Friday
            promo_ts = datetime(target_date.year, target_date.month, target_date.day,
                                10, 0, 0, tzinfo=timezone.utc)
            for i in range(5000):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                tmpl = self.rng.choice(TEMPLATES["promotional"])
                records.append(self._make_notification(
                    promo_ts, sub, "promotional", tmpl[0], tmpl[1], multiplier,
                ))

        # ── Subscription expiry (~1K/day) ──
        for i in range(1000):
            sub = pool[self.rng.randint(0, len(pool) - 1)]
            ts = datetime(target_date.year, target_date.month, target_date.day,
                          9, self.rng.randint(0, 59), 0, tzinfo=timezone.utc)
            tmpl = self.rng.choice(TEMPLATES["subscription_expiry"])
            records.append(self._make_notification(
                ts, sub, "subscription_expiry", tmpl[0], tmpl[1], multiplier,
            ))

        records.sort(key=lambda r: r["timestamp"])
        self.write_jsonl_gz(
            records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.jsonl.gz",
        )

        logger.info("push_day_complete", date=target_date.isoformat(), records=len(records))
        return len(records)


if __name__ == "__main__":
    PushNotificationsGenerator().generate_all()
