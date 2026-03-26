"""Player Events log schema — 7 event types, session-based event chains."""

from __future__ import annotations

from pydantic import BaseModel


class PlayerEventEntry(BaseModel):
    """Player event log entry — 7 event types in a session chain."""

    # ── META ──
    event_id: str
    event_type: str  # session_start | buffer_start | buffer_end | bitrate_change | error | seek | session_end
    timestamp: str  # ISO 8601
    session_id: str

    # ── USER & CONTENT ──
    user_id_hash: str  # SHA256
    device_type: str
    subscription_tier: str  # premium | standard | free
    content_id: str
    content_type: str  # live | vod
    channel: str | None = None

    # ── SESSION_START fields ──
    initial_bitrate_kbps: int | None = None
    startup_time_ms: int | None = None
    player_version: str | None = None
    cdn_provider: str | None = None  # medianova | akamai
    stream_url_hash: str | None = None  # SHA256

    # ── BUFFER fields ──
    position_ms: int | None = None
    buffer_duration_ms: int | None = None  # set on buffer_end
    buffer_ratio: float | None = None

    # ── BITRATE_CHANGE fields ──
    from_bitrate_kbps: int | None = None
    to_bitrate_kbps: int | None = None
    change_reason: str | None = None  # bandwidth | manual | error | startup

    # ── ERROR fields ──
    error_code: str | None = None  # EXO_2320 | AVP_1001 | NET_TIMEOUT | DRM_ERROR
    error_fatal: bool | None = None

    # ── SEEK fields ──
    seek_from_ms: int | None = None
    seek_to_ms: int | None = None

    # ── SESSION_END fields ──
    total_duration_ms: int | None = None
    watched_duration_ms: int | None = None
    completion_rate: float | None = None  # 0.0-1.0
    exit_reason: str | None = None  # user | error | network | app_close
    final_qoe_score: float | None = None  # 0.0-5.0


FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "event_type": "meta",
    "timestamp": "meta",
    "session_id": "meta",
    "user_id_hash": "user",
    "device_type": "user",
    "subscription_tier": "user",
    "content_id": "content",
    "content_type": "content",
    "channel": "content",
    "initial_bitrate_kbps": "session_start",
    "startup_time_ms": "session_start",
    "player_version": "session_start",
    "cdn_provider": "session_start",
    "stream_url_hash": "session_start",
    "position_ms": "buffer",
    "buffer_duration_ms": "buffer",
    "buffer_ratio": "buffer",
    "from_bitrate_kbps": "bitrate",
    "to_bitrate_kbps": "bitrate",
    "change_reason": "bitrate",
    "error_code": "error",
    "error_fatal": "error",
    "seek_from_ms": "seek",
    "seek_to_ms": "seek",
    "total_duration_ms": "session_end",
    "watched_duration_ms": "session_end",
    "completion_rate": "session_end",
    "exit_reason": "session_end",
    "final_qoe_score": "session_end",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique event identifier (UUID)",
    "event_type": "Player event type (session_start/buffer_start/buffer_end/bitrate_change/error/seek/session_end)",
    "timestamp": "Event timestamp in ISO 8601 format",
    "session_id": "Streaming session identifier (shared across all events in a session)",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "device_type": "Client device type",
    "subscription_tier": "User subscription tier (premium/standard/free)",
    "content_id": "Content identifier",
    "content_type": "Content type (live/vod)",
    "channel": "Streaming channel (for live content)",
    "initial_bitrate_kbps": "Initial stream bitrate at session start (kbps)",
    "startup_time_ms": "Time from play request to first frame rendered (ms)",
    "player_version": "Video player library version",
    "cdn_provider": "CDN provider serving the stream (medianova/akamai)",
    "stream_url_hash": "Stream URL (SHA256 hashed)",
    "position_ms": "Playback position when buffer event occurred (ms)",
    "buffer_duration_ms": "Duration of buffering event (ms, set on buffer_end)",
    "buffer_ratio": "Ratio of buffering time to total playback time",
    "from_bitrate_kbps": "Bitrate before quality change (kbps)",
    "to_bitrate_kbps": "Bitrate after quality change (kbps)",
    "change_reason": "Reason for bitrate change (bandwidth/manual/error/startup)",
    "error_code": "Player error code (EXO_2320/AVP_1001/NET_TIMEOUT/DRM_ERROR)",
    "error_fatal": "Whether the error terminated playback",
    "seek_from_ms": "Playback position before seek (ms)",
    "seek_to_ms": "Playback position after seek (ms)",
    "total_duration_ms": "Total session wall-clock duration (ms)",
    "watched_duration_ms": "Actual content watched duration (ms)",
    "completion_rate": "Fraction of content watched (0.0-1.0)",
    "exit_reason": "Reason session ended (user/error/network/app_close)",
    "final_qoe_score": "Computed QoE score for the session (0.0-5.0)",
}
