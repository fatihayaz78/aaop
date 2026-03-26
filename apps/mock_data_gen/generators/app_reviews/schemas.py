"""App Reviews schema — store ratings with Turkish content and sentiment."""

from __future__ import annotations

from pydantic import BaseModel


class AppReviewEntry(BaseModel):
    """App store review entry."""

    # ── META ──
    review_id: str  # REV-{12hex}
    platform: str  # ios | android
    timestamp: str  # ISO 8601
    app_version: str  # 4.2.1 | 4.2.0 | 4.1.9

    # ── CİHAZ ──
    device_model: str
    os_version: str
    country: str  # TR dominant
    language: str  # tr | en

    # ── DEĞERLENDİRME ──
    rating: int  # 1-5
    title: str | None = None  # Turkish
    body: str  # Turkish dominant

    # ── ANALİZ ──
    sentiment: str  # positive | neutral | negative
    category: str  # buffering | login | content | payment | crash | ui | drm | other
    topics: list[str]
    language_detected: str  # tr | en

    # ── YANIT ──
    developer_response: bool = False
    developer_response_text: str | None = None
    developer_response_at: str | None = None

    # ── BAĞLAM ──
    triggered_by_event: str | None = None  # cdn_outage | fairplay_issue | elclasico | normal


FIELD_CATEGORIES: dict[str, str] = {
    "review_id": "meta", "platform": "meta",
    "timestamp": "meta", "app_version": "meta",
    "device_model": "device", "os_version": "device",
    "country": "device", "language": "device",
    "rating": "review", "title": "review", "body": "review",
    "sentiment": "analysis", "category": "analysis",
    "topics": "analysis", "language_detected": "analysis",
    "developer_response": "response", "developer_response_text": "response",
    "developer_response_at": "response",
    "triggered_by_event": "context",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "review_id": "Unique review ID (REV-{12hex})",
    "platform": "App store platform (ios/android)",
    "timestamp": "Review submission timestamp",
    "app_version": "App version reviewed",
    "device_model": "User device model",
    "os_version": "Operating system version",
    "country": "Reviewer country code",
    "language": "Review language (tr/en)",
    "rating": "Star rating (1-5)",
    "title": "Review title (optional, Turkish)",
    "body": "Review body text (Turkish dominant)",
    "sentiment": "Detected sentiment (positive/neutral/negative)",
    "category": "Issue category (buffering/login/content/payment/crash/ui/drm/other)",
    "topics": "Detected topic tags",
    "language_detected": "Detected language of review text",
    "developer_response": "Whether developer responded",
    "developer_response_text": "Developer response text",
    "developer_response_at": "Developer response timestamp",
    "triggered_by_event": "Calendar event that triggered the review",
}
