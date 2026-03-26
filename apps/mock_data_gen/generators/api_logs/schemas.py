"""API Logs schema — 13 endpoints, request/response tracking."""

from __future__ import annotations

from pydantic import BaseModel


class APILogEntry(BaseModel):
    """API gateway access log entry."""

    # ── META ──
    event_id: str
    timestamp: str  # ISO 8601
    request_id: str  # correlation with DRM/Player

    # ── REQUEST ──
    endpoint: str
    method: str  # GET | POST
    status_code: int
    response_time_ms: int

    # ── USER ──
    user_id_hash: str | None = None  # SHA256, null before login
    subscription_tier: str | None = None
    device_type: str
    app_version: str | None = None
    ip_hash: str  # SHA256
    country_code: str

    # ── RESPONSE ──
    error_code: str | None = None
    error_message: str | None = None
    cache_hit: bool | None = None


ENDPOINTS = [
    "/auth/login", "/auth/token/refresh", "/auth/logout",
    "/content/stream", "/content/search", "/content/detail",
    "/subscription/check", "/subscription/upgrade", "/subscription/cancel",
    "/epg/schedule", "/epg/now-playing",
    "/user/profile", "/user/preferences",
]

FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "timestamp": "meta",
    "request_id": "meta",
    "endpoint": "request",
    "method": "request",
    "status_code": "request",
    "response_time_ms": "request",
    "user_id_hash": "user",
    "subscription_tier": "user",
    "device_type": "user",
    "app_version": "user",
    "ip_hash": "user",
    "country_code": "user",
    "error_code": "response",
    "error_message": "response",
    "cache_hit": "response",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique event identifier (UUID)",
    "timestamp": "Request timestamp in ISO 8601 format",
    "request_id": "Unique request ID for cross-service correlation",
    "endpoint": "API endpoint path",
    "method": "HTTP method (GET/POST)",
    "status_code": "HTTP response status code",
    "response_time_ms": "Server response time in milliseconds",
    "user_id_hash": "User identifier (SHA256 hashed, null before login)",
    "subscription_tier": "User subscription tier (premium/standard/free)",
    "device_type": "Client device type",
    "app_version": "Client application version",
    "ip_hash": "Client IP address (SHA256 hashed)",
    "country_code": "Client country code (ISO 3166-1 alpha-2)",
    "error_code": "Error code for non-2xx responses",
    "error_message": "Error description for non-2xx responses",
    "cache_hit": "Whether response was served from cache",
}
