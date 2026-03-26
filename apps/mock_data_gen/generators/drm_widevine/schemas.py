"""Widevine DRM log schema — 4 event types, 7 categories."""

from __future__ import annotations

from pydantic import BaseModel


class WidevineLogEntry(BaseModel):
    """Widevine DRM license server log entry."""

    # ── META ──
    event_id: str
    event_type: str  # license_request | license_renewal | license_validation | license_error
    timestamp: str  # ISO 8601
    drm_server: str  # drm.ssport.com.tr

    # ── SESSION ──
    session_id: str
    device_id_hash: str  # SHA256
    user_id_hash: str  # SHA256
    subscription_tier: str  # premium | standard | free

    # ── CONTENT ──
    content_id: str
    content_type: str  # live | vod
    channel: str | None = None
    pssh_data: str | None = None  # SHA256

    # ── DEVICE ──
    device_type: str  # android | web_chrome | web_firefox | android_tv | tizen_os | webos
    widevine_security_level: str  # L1 | L2 | L3
    os_version: str | None = None
    browser: str | None = None
    app_version: str | None = None

    # ── LICENSE ──
    license_type: str  # streaming | offline | persistent
    license_duration_s: int | None = None
    renewal_interval_s: int | None = 300
    policy_name: str | None = None

    # ── RESPONSE ──
    status: str  # success | failed | timeout | rejected
    response_time_ms: int
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0

    # ── NETWORK ──
    country_code: str
    isp: str | None = None
    ip_hash: str  # SHA256


FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "event_type": "meta",
    "timestamp": "meta",
    "drm_server": "meta",
    "session_id": "session",
    "device_id_hash": "session",
    "user_id_hash": "session",
    "subscription_tier": "session",
    "content_id": "content",
    "content_type": "content",
    "channel": "content",
    "pssh_data": "content",
    "device_type": "device",
    "widevine_security_level": "device",
    "os_version": "device",
    "browser": "device",
    "app_version": "device",
    "license_type": "license",
    "license_duration_s": "license",
    "renewal_interval_s": "license",
    "policy_name": "license",
    "status": "response",
    "response_time_ms": "response",
    "error_code": "response",
    "error_message": "response",
    "retry_count": "response",
    "country_code": "network",
    "isp": "network",
    "ip_hash": "network",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique event identifier (UUID)",
    "event_type": "DRM event type (license_request/renewal/validation/error)",
    "timestamp": "Event timestamp in ISO 8601 format",
    "drm_server": "DRM license server hostname",
    "session_id": "Streaming session identifier",
    "device_id_hash": "Device identifier (SHA256 hashed)",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "subscription_tier": "User subscription tier (premium/standard/free)",
    "content_id": "Content identifier",
    "content_type": "Content type (live/vod)",
    "channel": "Streaming channel (for live content)",
    "pssh_data": "Protection System Specific Header data (SHA256 hashed)",
    "device_type": "Client device type",
    "widevine_security_level": "Widevine security level (L1/L2/L3)",
    "os_version": "Client operating system version",
    "browser": "Browser name and version (for web clients)",
    "app_version": "Application version (for native apps)",
    "license_type": "License type (streaming/offline/persistent)",
    "license_duration_s": "License validity duration in seconds",
    "renewal_interval_s": "License renewal interval in seconds (default 300)",
    "policy_name": "DRM policy name applied",
    "status": "Request status (success/failed/timeout/rejected)",
    "response_time_ms": "Server response time in milliseconds",
    "error_code": "Error code for failed requests",
    "error_message": "Error description for failed requests",
    "retry_count": "Number of retry attempts",
    "country_code": "Client country code (ISO 3166-1 alpha-2)",
    "isp": "Client Internet Service Provider",
    "ip_hash": "Client IP address (SHA256 hashed)",
}
