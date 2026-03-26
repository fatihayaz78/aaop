"""NPAW Analytics schema — post-session QoE aggregates, correlated with Player Events."""

from __future__ import annotations

from pydantic import BaseModel


class NPAWSessionEntry(BaseModel):
    """NPAW (Youbora) post-session analytics aggregate."""

    # ── META ──
    event_id: str
    session_id: str  # MATCHES PlayerEvents session_id
    timestamp: str  # ISO 8601

    # ── USER & CONTENT ──
    user_id_hash: str  # SHA256
    device_type: str
    subscription_tier: str
    content_id: str
    content_type: str  # live | vod
    channel: str | None = None
    cdn_provider: str
    country_code: str

    # ── QoE METRICS ──
    startup_time_ms: int
    total_buffering_ms: int
    rebuffering_ratio: float
    avg_bitrate_kbps: int
    num_bitrate_changes: int
    num_errors: int
    num_seeks: int

    # ── SESSION SUMMARY ──
    session_duration_ms: int
    watched_duration_ms: int
    completion_rate: float
    exit_before_video_start: bool
    unique_renditions_played: int

    # ── YOUBORA SCORES ──
    youbora_score: float  # 0.0-10.0
    qoe_score: float  # 0.0-5.0 (≈ PlayerEvents final_qoe_score ±0.1)


FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "session_id": "meta",
    "timestamp": "meta",
    "user_id_hash": "user",
    "device_type": "user",
    "subscription_tier": "user",
    "content_id": "content",
    "content_type": "content",
    "channel": "content",
    "cdn_provider": "content",
    "country_code": "network",
    "startup_time_ms": "qoe",
    "total_buffering_ms": "qoe",
    "rebuffering_ratio": "qoe",
    "avg_bitrate_kbps": "qoe",
    "num_bitrate_changes": "qoe",
    "num_errors": "qoe",
    "num_seeks": "qoe",
    "session_duration_ms": "session",
    "watched_duration_ms": "session",
    "completion_rate": "session",
    "exit_before_video_start": "session",
    "unique_renditions_played": "session",
    "youbora_score": "score",
    "qoe_score": "score",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique NPAW event identifier (UUID)",
    "session_id": "Session ID matching Player Events (correlation key)",
    "timestamp": "Session end timestamp in ISO 8601 format",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "device_type": "Client device type",
    "subscription_tier": "User subscription tier (premium/standard/free)",
    "content_id": "Content identifier",
    "content_type": "Content type (live/vod)",
    "channel": "Streaming channel (for live content)",
    "cdn_provider": "CDN provider (medianova/akamai)",
    "country_code": "Client country code (ISO 3166-1 alpha-2)",
    "startup_time_ms": "Time to first frame in milliseconds",
    "total_buffering_ms": "Total buffering duration in milliseconds",
    "rebuffering_ratio": "Buffering time / watched time ratio",
    "avg_bitrate_kbps": "Average stream bitrate in kbps",
    "num_bitrate_changes": "Number of quality switches during session",
    "num_errors": "Number of player errors during session",
    "num_seeks": "Number of seek operations during session",
    "session_duration_ms": "Total session wall-clock duration in milliseconds",
    "watched_duration_ms": "Actual content watched duration in milliseconds",
    "completion_rate": "Fraction of content watched (0.0-1.0)",
    "exit_before_video_start": "Whether user left before first frame rendered",
    "unique_renditions_played": "Number of distinct bitrate renditions played",
    "youbora_score": "Youbora experience score (0.0-10.0)",
    "qoe_score": "Quality of Experience score (0.0-5.0, matches Player Events ±0.1)",
}
