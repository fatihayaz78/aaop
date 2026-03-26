"""Push Notifications schema — 10 notification types, Turkish content."""

from __future__ import annotations

from pydantic import BaseModel


class PushNotificationEntry(BaseModel):
    """Push notification log entry."""

    # ── META ──
    notification_id: str  # NTF-{12hex}
    campaign_id: str | None = None  # MKT-{8hex}
    timestamp: str  # ISO 8601 — send time
    delivered_at: str | None = None
    opened_at: str | None = None

    # ── ABONE ──
    subscriber_id: str  # matches CRM
    user_id_hash: str  # SHA256
    subscription_tier: str
    device_token_hash: str  # SHA256
    platform: str  # ios | android | web
    app_version: str | None = None

    # ── BİLDİRİM ──
    notification_type: str
    title: str  # Turkish
    body: str  # Turkish
    deep_link: str | None = None
    image_url: str | None = None

    # ── İÇERİK BAĞLAMI ──
    content_id: str | None = None
    channel_id: str | None = None
    competition: str | None = None

    # ── TESLİMAT ──
    delivered: bool = True
    opened: bool = False
    delivery_latency_ms: int | None = None
    failure_reason: str | None = None  # token_expired | app_uninstalled | rate_limited | network_error

    # ── ETKİLEŞİM ──
    ctr: float | None = None
    conversion: bool | None = None
    conversion_content_id: str | None = None


FIELD_CATEGORIES: dict[str, str] = {
    "notification_id": "meta", "campaign_id": "meta",
    "timestamp": "meta", "delivered_at": "meta", "opened_at": "meta",
    "subscriber_id": "subscriber", "user_id_hash": "subscriber",
    "subscription_tier": "subscriber", "device_token_hash": "subscriber",
    "platform": "subscriber", "app_version": "subscriber",
    "notification_type": "notification", "title": "notification",
    "body": "notification", "deep_link": "notification", "image_url": "notification",
    "content_id": "context", "channel_id": "context", "competition": "context",
    "delivered": "delivery", "opened": "delivery",
    "delivery_latency_ms": "delivery", "failure_reason": "delivery",
    "ctr": "engagement", "conversion": "engagement",
    "conversion_content_id": "engagement",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "notification_id": "Unique notification ID (NTF-{12hex})",
    "campaign_id": "Marketing campaign ID (MKT-{8hex})",
    "timestamp": "Notification send timestamp",
    "delivered_at": "Delivery confirmation timestamp",
    "opened_at": "User open timestamp",
    "subscriber_id": "Subscriber ID (matches CRM)",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "subscription_tier": "Subscription tier",
    "device_token_hash": "Push token (SHA256 hashed)",
    "platform": "Device platform (ios/android/web)",
    "app_version": "Application version",
    "notification_type": "Notification type (match_reminder/match_starting/score_update/system_alert/service_restored/subscription_expiry/payment_failed/promotional/new_content/personalized)",
    "title": "Notification title (Turkish)",
    "body": "Notification body (Turkish)",
    "deep_link": "Deep link URL for in-app navigation",
    "image_url": "Notification image URL",
    "content_id": "Related content identifier",
    "channel_id": "Related channel identifier",
    "competition": "Related sports competition",
    "delivered": "Whether notification was delivered",
    "opened": "Whether notification was opened by user",
    "delivery_latency_ms": "Delivery latency in milliseconds",
    "failure_reason": "Delivery failure reason",
    "ctr": "Click-through rate for this notification batch",
    "conversion": "Whether user converted (watched content)",
    "conversion_content_id": "Content watched after notification",
}
