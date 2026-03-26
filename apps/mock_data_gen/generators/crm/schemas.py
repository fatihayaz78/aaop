"""CRM/Subscriber schemas — 485K subscriber base + daily deltas."""

from __future__ import annotations

from pydantic import BaseModel


class SubscriberProfile(BaseModel):
    """Full subscriber profile for CRM base export."""

    # ── KİMLİK ──
    subscriber_id: str  # SUB-{8hex}
    user_id_hash: str  # SHA256
    email_hash: str  # SHA256
    phone_hash: str  # SHA256
    created_at: str  # ISO 8601

    # ── DEMOGRAFİ ──
    name: str
    age_group: str  # 18-24 | 25-34 | 35-44 | 45-54 | 55+
    gender: str  # M | F | unspecified
    country: str
    city: str
    timezone: str  # Europe/Istanbul

    # ── ABONELİK ──
    subscription_tier: str  # premium | standard | free
    subscription_status: str  # active | suspended | cancelled | trial
    subscription_start_date: str
    subscription_end_date: str | None = None
    trial_end_date: str | None = None
    auto_renew: bool = True
    payment_method: str
    payment_cycle: str  # monthly | annual
    monthly_price_tl: float  # premium:299 | standard:149 | free:0

    # ── AKTİVİTE (son 30 gün) ──
    last_active_date: str
    last_login_date: str
    total_sessions_30d: int
    total_watch_hours_30d: float
    total_watch_hours_90d: float
    avg_session_duration_min: float
    peak_viewing_hour: int  # 0-23
    days_active_30d: int

    # ── CİHAZ ──
    preferred_device: str
    registered_device_count: int  # 1-4
    devices: list[str]

    # ── İÇERİK TERCİHİ ──
    favorite_content_type: str  # live_sport | vod | news | magazine
    favorite_teams: list[str]
    favorite_channels: list[str]
    content_language: str  # tr | en

    # ── ÖDEME GEÇMİŞİ ──
    failed_payment_count_90d: int
    last_payment_date: str
    last_payment_status: str  # success | failed | pending
    last_failed_payment_reason: str | None = None
    lifetime_payment_total_tl: float

    # ── DESTEK ──
    support_tickets_90d: int
    last_ticket_category: str | None = None
    app_store_rating_given: int | None = None  # 1-5
    nps_score: int | None = None  # 0-10

    # ── CHURN ──
    churn_risk_score: float  # 0.0-1.0
    churn_risk_category: str  # low | medium | high | critical
    churn_reason_primary: str | None = None
    predicted_churn_date: str | None = None
    retention_campaign_eligible: bool = False
    last_churn_risk_update: str

    # ── ACQUISITION ──
    acquisition_channel: str  # organic | social_media | tv_ad | partner | referral
    referrer_id: str | None = None
    promo_code_used: str | None = None
    first_content_watched: str | None = None


class SubscriberDailyDelta(BaseModel):
    """Daily subscriber state change record."""

    subscriber_id: str
    date: str
    churn_risk_score: float
    churn_risk_category: str
    total_watch_hours_30d: float
    total_sessions_30d: int
    days_active_30d: int
    last_active_date: str
    failed_payment_count_90d: int
    support_tickets_90d: int
    subscription_status: str
    updated_fields: list[str]


FIELD_CATEGORIES: dict[str, str] = {
    # SubscriberProfile fields
    "subscriber_id": "identity", "user_id_hash": "identity",
    "email_hash": "identity", "phone_hash": "identity", "created_at": "identity",
    "name": "demographics", "age_group": "demographics", "gender": "demographics",
    "country": "demographics", "city": "demographics", "timezone": "demographics",
    "subscription_tier": "subscription", "subscription_status": "subscription",
    "subscription_start_date": "subscription", "subscription_end_date": "subscription",
    "trial_end_date": "subscription", "auto_renew": "subscription",
    "payment_method": "subscription", "payment_cycle": "subscription",
    "monthly_price_tl": "subscription",
    "last_active_date": "activity", "last_login_date": "activity",
    "total_sessions_30d": "activity", "total_watch_hours_30d": "activity",
    "total_watch_hours_90d": "activity", "avg_session_duration_min": "activity",
    "peak_viewing_hour": "activity", "days_active_30d": "activity",
    "preferred_device": "device", "registered_device_count": "device", "devices": "device",
    "favorite_content_type": "preference", "favorite_teams": "preference",
    "favorite_channels": "preference", "content_language": "preference",
    "failed_payment_count_90d": "payment", "last_payment_date": "payment",
    "last_payment_status": "payment", "last_failed_payment_reason": "payment",
    "lifetime_payment_total_tl": "payment",
    "support_tickets_90d": "support", "last_ticket_category": "support",
    "app_store_rating_given": "support", "nps_score": "support",
    "churn_risk_score": "churn", "churn_risk_category": "churn",
    "churn_reason_primary": "churn", "predicted_churn_date": "churn",
    "retention_campaign_eligible": "churn", "last_churn_risk_update": "churn",
    "acquisition_channel": "acquisition", "referrer_id": "acquisition",
    "promo_code_used": "acquisition", "first_content_watched": "acquisition",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "subscriber_id": "Unique subscriber ID (SUB-{8hex})",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "email_hash": "Email address (SHA256 hashed)",
    "phone_hash": "Phone number (SHA256 hashed)",
    "created_at": "Account creation timestamp",
    "name": "Subscriber display name",
    "age_group": "Age bracket (18-24/25-34/35-44/45-54/55+)",
    "gender": "Gender (M/F/unspecified)",
    "country": "Country code", "city": "City name",
    "timezone": "Timezone (Europe/Istanbul)",
    "subscription_tier": "Subscription tier (premium/standard/free)",
    "subscription_status": "Status (active/suspended/cancelled/trial)",
    "subscription_start_date": "Subscription start date",
    "subscription_end_date": "Subscription end date (if cancelled)",
    "trial_end_date": "Trial period end date",
    "auto_renew": "Auto-renewal enabled",
    "payment_method": "Payment method type",
    "payment_cycle": "Billing cycle (monthly/annual)",
    "monthly_price_tl": "Monthly subscription price in TRY",
    "last_active_date": "Last platform activity date",
    "last_login_date": "Last login date",
    "total_sessions_30d": "Total sessions in last 30 days",
    "total_watch_hours_30d": "Total watch hours in last 30 days",
    "total_watch_hours_90d": "Total watch hours in last 90 days",
    "avg_session_duration_min": "Average session duration in minutes",
    "peak_viewing_hour": "Most common viewing hour (0-23 UTC)",
    "days_active_30d": "Days with activity in last 30 days",
    "preferred_device": "Most used device type",
    "registered_device_count": "Number of registered devices",
    "devices": "List of registered device types",
    "favorite_content_type": "Preferred content type",
    "favorite_teams": "Favorite sports teams",
    "favorite_channels": "Favorite channels",
    "content_language": "Preferred content language (tr/en)",
    "failed_payment_count_90d": "Failed payments in last 90 days",
    "last_payment_date": "Last payment date",
    "last_payment_status": "Last payment status",
    "last_failed_payment_reason": "Reason for last payment failure",
    "lifetime_payment_total_tl": "Total lifetime payments in TRY",
    "support_tickets_90d": "Support tickets in last 90 days",
    "last_ticket_category": "Last support ticket category",
    "app_store_rating_given": "App store rating (1-5)",
    "nps_score": "Net Promoter Score (0-10)",
    "churn_risk_score": "Churn risk score (0.0-1.0)",
    "churn_risk_category": "Risk category (low/medium/high/critical)",
    "churn_reason_primary": "Primary churn risk factor",
    "predicted_churn_date": "Predicted churn date",
    "retention_campaign_eligible": "Eligible for retention campaign",
    "last_churn_risk_update": "Last churn risk calculation date",
    "acquisition_channel": "How subscriber was acquired",
    "referrer_id": "Referring subscriber ID",
    "promo_code_used": "Promotional code used at signup",
    "first_content_watched": "First content watched after signup",
}
