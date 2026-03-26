"""CRM/Subscriber generator — 485K base CSV + daily delta JSONL.gz.

Output:
  crm/subscribers_base.csv — full subscriber profiles (generated once)
  crm/daily_updates/YYYY/MM/DD/{YYYY-MM-DD}_delta.jsonl.gz — daily changes
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator, PERIOD_START
from apps.mock_data_gen.generators.calendar_events import get_anomaly_for_date

logger = structlog.get_logger(__name__)

TURKISH_NAMES_M = ["Ahmet", "Mehmet", "Ali", "Mustafa", "Emre", "Burak", "Cem", "Oğuz", "Kaan", "Serkan"]
TURKISH_NAMES_F = ["Ayşe", "Fatma", "Elif", "Zeynep", "Merve", "Selin", "Deniz", "Gamze", "Ebru", "Başak"]
TEAMS = ["Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Real Madrid", "Barcelona", "Inter"]
CHANNELS_LIST = ["s_sport_1", "s_sport_2", "s_plus_live_1", "cnn_turk", "trt_spor", "a_spor"]
PAYMENT_METHODS = ["credit_card", "debit_card", "bank_transfer", "mobile_payment"]
ACQUISITION_CHANNELS = ["organic", "social_media", "tv_ad", "partner", "referral"]
TICKET_CATEGORIES = ["billing", "technical", "content", "account", "feedback"]
PRICE_MAP = {"premium": 299.0, "standard": 149.0, "free": 0.0}


def compute_churn_risk(days_active: int, failed_payments: int, tickets: int,
                       nps: int | None) -> float:
    """Compute churn risk score based on subscriber signals."""
    score = 0.0
    if days_active == 0:
        score += 0.40
    elif days_active < 5:
        score += 0.25
    if failed_payments >= 3:
        score += 0.30
    elif failed_payments == 2:
        score += 0.20
    elif failed_payments == 1:
        score += 0.10
    if tickets >= 3:
        score += 0.15
    if nps is not None and nps <= 3:
        score += 0.10
    return min(1.0, round(score, 2))


def churn_category(score: float) -> str:
    if score < 0.3:
        return "low"
    if score < 0.5:
        return "medium"
    if score < 0.75:
        return "high"
    return "critical"


class CRMGenerator(BaseGenerator):
    """Generates CRM subscriber base and daily delta files."""

    @property
    def source_name(self) -> str:
        return "crm"

    def _generate_profile(self, sub, ref_date: date) -> dict:
        """Generate a full SubscriberProfile dict from a Subscriber."""
        gender = self.rng.choices(["M", "F", "unspecified"], weights=[0.55, 0.40, 0.05], k=1)[0]
        if gender == "M":
            name = self.rng.choice(TURKISH_NAMES_M)
        elif gender == "F":
            name = self.rng.choice(TURKISH_NAMES_F)
        else:
            name = self.rng.choice(TURKISH_NAMES_M + TURKISH_NAMES_F)

        age_group = self.rng.choices(
            ["18-24", "25-34", "35-44", "45-54", "55+"],
            weights=[0.15, 0.35, 0.25, 0.15, 0.10], k=1,
        )[0]

        # Subscription dates
        months_ago = self.rng.randint(1, 36)
        start_date = ref_date - timedelta(days=months_ago * 30)
        status = self.rng.choices(
            ["active", "suspended", "cancelled", "trial"],
            weights=[0.82, 0.05, 0.08, 0.05], k=1,
        )[0]

        # Activity
        days_active = self.rng.randint(0, 30)
        sessions = self.rng.randint(0, days_active * 3) if days_active > 0 else 0
        watch_30d = round(sessions * self.rng.uniform(0.3, 2.0), 1)
        watch_90d = round(watch_30d * self.rng.uniform(2.5, 3.5), 1)
        avg_dur = round(self.rng.uniform(15, 120), 1) if sessions > 0 else 0.0

        # Payment
        failed_payments = self.rng.choices([0, 1, 2, 3], weights=[0.85, 0.08, 0.04, 0.03], k=1)[0]
        last_pay_status = "success" if failed_payments == 0 else self.rng.choice(["success", "failed"])
        fail_reason = None
        if last_pay_status == "failed":
            fail_reason = self.rng.choice(["insufficient_funds", "card_expired", "bank_reject"])

        lifetime_pay = round(months_ago * PRICE_MAP[sub.tier] * self.rng.uniform(0.8, 1.0), 2)

        # Support
        tickets = self.rng.choices([0, 1, 2, 3, 4], weights=[0.70, 0.15, 0.08, 0.05, 0.02], k=1)[0]
        nps = self.rng.randint(0, 10) if self.rng.random() < 0.40 else None
        rating = self.rng.randint(1, 5) if self.rng.random() < 0.20 else None

        # Churn
        churn_score = compute_churn_risk(days_active, failed_payments, tickets, nps)

        devices = [sub.device_type]
        dev_count = self.rng.randint(1, 4)
        extra_devs = ["android", "ios", "web_chrome", "tizen_os", "apple_tv"]
        for _ in range(dev_count - 1):
            d = self.rng.choice(extra_devs)
            if d not in devices:
                devices.append(d)

        country = sub.country if sub.country != "OTHER" else "GB"

        return {
            "subscriber_id": f"SUB-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:8]}",
            "user_id_hash": hashlib.sha256(sub.user_id.encode()).hexdigest()[:32],
            "email_hash": sub.email_hash[:32],
            "phone_hash": hashlib.sha256(f"phone_{sub.user_id}".encode()).hexdigest()[:32],
            "created_at": start_date.isoformat(),
            "name": name,
            "age_group": age_group,
            "gender": gender,
            "country": country,
            "city": sub.city,
            "timezone": "Europe/Istanbul",
            "subscription_tier": sub.tier,
            "subscription_status": status,
            "subscription_start_date": start_date.isoformat(),
            "subscription_end_date": (ref_date - timedelta(days=self.rng.randint(1, 30))).isoformat() if status == "cancelled" else None,
            "trial_end_date": (start_date + timedelta(days=14)).isoformat() if status == "trial" else None,
            "auto_renew": status == "active",
            "payment_method": self.rng.choice(PAYMENT_METHODS),
            "payment_cycle": self.rng.choices(["monthly", "annual"], weights=[0.75, 0.25], k=1)[0],
            "monthly_price_tl": PRICE_MAP[sub.tier],
            "last_active_date": (ref_date - timedelta(days=30 - days_active)).isoformat() if days_active > 0 else (ref_date - timedelta(days=60)).isoformat(),
            "last_login_date": (ref_date - timedelta(days=self.rng.randint(0, 30))).isoformat(),
            "total_sessions_30d": sessions,
            "total_watch_hours_30d": watch_30d,
            "total_watch_hours_90d": watch_90d,
            "avg_session_duration_min": avg_dur,
            "peak_viewing_hour": self.rng.randint(17, 23),
            "days_active_30d": days_active,
            "preferred_device": sub.device_type,
            "registered_device_count": len(devices),
            "devices": devices,
            "favorite_content_type": self.rng.choices(
                ["live_sport", "vod", "news", "magazine"],
                weights=[0.55, 0.25, 0.12, 0.08], k=1,
            )[0],
            "favorite_teams": self.rng.sample(TEAMS, min(3, len(TEAMS))),
            "favorite_channels": self.rng.sample(CHANNELS_LIST, min(3, len(CHANNELS_LIST))),
            "content_language": self.rng.choices(["tr", "en"], weights=[0.92, 0.08], k=1)[0],
            "failed_payment_count_90d": failed_payments,
            "last_payment_date": (ref_date - timedelta(days=self.rng.randint(1, 30))).isoformat(),
            "last_payment_status": last_pay_status,
            "last_failed_payment_reason": fail_reason,
            "lifetime_payment_total_tl": lifetime_pay,
            "support_tickets_90d": tickets,
            "last_ticket_category": self.rng.choice(TICKET_CATEGORIES) if tickets > 0 else None,
            "app_store_rating_given": rating,
            "nps_score": nps,
            "churn_risk_score": churn_score,
            "churn_risk_category": churn_category(churn_score),
            "churn_reason_primary": "inactivity" if days_active < 5 else ("payment_failure" if failed_payments >= 2 else None),
            "predicted_churn_date": (ref_date + timedelta(days=self.rng.randint(15, 60))).isoformat() if churn_score >= 0.5 else None,
            "retention_campaign_eligible": churn_score >= 0.3,
            "last_churn_risk_update": ref_date.isoformat(),
            "acquisition_channel": self.rng.choice(ACQUISITION_CHANNELS),
            "referrer_id": f"SUB-{self.rng.randint(10000, 99999):05x}" if self.rng.random() < 0.15 else None,
            "promo_code_used": f"PROMO{self.rng.randint(100, 999)}" if self.rng.random() < 0.20 else None,
            "first_content_watched": self.rng.choice(["La Liga", "EuroLeague", "UFC", "Serie A", "News"]),
        }

    def generate_base(self, pool_size: int | None = None) -> int:
        """Generate subscribers_base.csv."""
        pool = self.subscriber_pool
        size = pool_size or len(pool)
        profiles: list[dict] = []

        for i in range(size):
            sub = pool[i]
            profiles.append(self._generate_profile(sub, PERIOD_START))

        self.write_csv(profiles, filename="subscribers_base.csv")
        logger.info("crm_base_generated", count=len(profiles))
        return len(profiles)

    def generate_day(self, target_date: date) -> int:
        """Generate daily delta for changed subscribers."""
        anomaly = get_anomaly_for_date(target_date)
        pool = self.subscriber_pool
        deltas: list[dict] = []

        # Determine which subscribers get updates
        # ~5-10% of subscribers get daily changes
        update_pct = 0.07
        if anomaly == "holiday":
            update_pct = 0.03

        # Calendar-specific effects
        is_cdn_outage_aftermath = (target_date == date(2026, 3, 1))
        is_fairplay_aftermath = (target_date == date(2026, 3, 16))
        is_elclasico_aftermath = (target_date == date(2026, 3, 5))
        is_holiday = anomaly == "holiday"

        num_updates = int(len(pool) * update_pct)

        for i in range(num_updates):
            idx = self.rng.randint(0, len(pool) - 1)
            sub = pool[idx]
            sub_id = f"SUB-{hashlib.sha256(sub.user_id.encode()).hexdigest()[:8]}"

            # Base metrics
            days_active = self.rng.randint(0, 30)
            sessions = self.rng.randint(0, days_active * 3) if days_active > 0 else 0
            watch_30d = round(sessions * self.rng.uniform(0.3, 2.0), 1)
            failed_payments = self.rng.choices([0, 1, 2, 3], weights=[0.85, 0.08, 0.04, 0.03], k=1)[0]
            tickets = self.rng.choices([0, 1, 2, 3], weights=[0.75, 0.13, 0.07, 0.05], k=1)[0]
            nps = self.rng.randint(0, 10) if self.rng.random() < 0.3 else None

            churn = compute_churn_risk(days_active, failed_payments, tickets, nps)
            updated_fields = ["churn_risk_score", "days_active_30d", "total_watch_hours_30d"]

            # Calendar effects
            if is_cdn_outage_aftermath and i < 38000 * update_pct:
                churn = min(1.0, churn + 0.15)
                tickets += 1
                updated_fields.extend(["support_tickets_90d"])

            if is_fairplay_aftermath and sub.device_type in ("ios", "apple_tv"):
                churn = min(1.0, churn + 0.20)
                updated_fields.extend(["churn_risk_score"])

            if is_elclasico_aftermath and self.rng.random() < 0.15:
                churn = min(1.0, churn + 0.10)

            if is_holiday and days_active < 3:
                churn = min(1.0, churn + 0.05)

            last_active = (target_date - timedelta(days=30 - days_active)).isoformat() if days_active > 0 else (target_date - timedelta(days=60)).isoformat()

            deltas.append({
                "subscriber_id": sub_id,
                "date": target_date.isoformat(),
                "churn_risk_score": round(churn, 2),
                "churn_risk_category": churn_category(churn),
                "total_watch_hours_30d": watch_30d,
                "total_sessions_30d": sessions,
                "days_active_30d": days_active,
                "last_active_date": last_active,
                "failed_payment_count_90d": failed_payments,
                "support_tickets_90d": tickets,
                "subscription_status": "active",
                "updated_fields": updated_fields,
            })

        if deltas:
            self.write_jsonl_gz(
                deltas,
                "daily_updates",
                target_date.strftime("%Y"),
                target_date.strftime("%m"),
                target_date.strftime("%d"),
                filename=f"{target_date.isoformat()}_delta.jsonl.gz",
            )

        logger.info("crm_delta_generated", date=target_date.isoformat(), deltas=len(deltas))
        return len(deltas)

    def run(self) -> None:
        """Generate base (if needed) + full date range."""
        base_path = self.output_root / self.source_name / "subscribers_base.csv"
        if not base_path.exists():
            self.generate_base()
        self.generate_all()


if __name__ == "__main__":
    CRMGenerator().generate_all()
