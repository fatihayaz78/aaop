"""Origin Server log schema — 4 event types, correlated with Medianova."""

from __future__ import annotations

from pydantic import BaseModel


class OriginLogEntry(BaseModel):
    """Origin server log entry — 4 event types."""

    # ── COMMON ──
    event_id: str
    event_type: str  # cdn_miss | hls_dash_fetch | health_check | transcoder_event
    timestamp: str  # ISO 8601
    origin_host: str  # origin-1.ssport.com.tr | origin-2.ssport.com.tr

    # ── REQUEST (cdn_miss + hls_dash_fetch) ──
    request_method: str | None = None
    request_uri: str | None = None
    http_protocol: str | None = None
    cdn_pop: str | None = None  # edge node that sent the request
    medianova_req_id: str | None = None  # CORRELATION KEY

    # ── RESPONSE ──
    status_code: int | None = None
    response_time_ms: int | None = None
    bytes_sent: int | None = None
    cache_control_header: str | None = None
    origin_load_pct: float | None = None  # 0-100

    # ── STREAM INFO (hls_dash_fetch) ──
    channel: str | None = None
    stream_type: str | None = None  # live | vod
    manifest_type: str | None = None  # hls_master | hls_media | dash_mpd | segment
    segment_number: int | None = None
    bitrate_kbps: int | None = None
    duration_ms: int | None = None

    # ── HEALTH CHECK ──
    health_status: str | None = None  # healthy | degraded | unhealthy
    check_source: str | None = None  # medianova | internal
    latency_ms: int | None = None

    # ── TRANSCODER EVENT ──
    encoder_id: str | None = None  # enc-01 | enc-02 | enc-03
    input_stream: str | None = None
    output_profiles: list[str] | None = None
    transcoder_status: str | None = None  # started | running | error | stopped
    error_message: str | None = None
    keyframe_interval_ms: int | None = None


FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "event_type": "meta",
    "timestamp": "meta",
    "origin_host": "meta",
    "request_method": "request",
    "request_uri": "request",
    "http_protocol": "request",
    "cdn_pop": "request",
    "medianova_req_id": "request",
    "status_code": "response",
    "response_time_ms": "response",
    "bytes_sent": "response",
    "cache_control_header": "response",
    "origin_load_pct": "response",
    "channel": "stream",
    "stream_type": "stream",
    "manifest_type": "stream",
    "segment_number": "stream",
    "bitrate_kbps": "stream",
    "duration_ms": "stream",
    "health_status": "health",
    "check_source": "health",
    "latency_ms": "health",
    "encoder_id": "transcoder",
    "input_stream": "transcoder",
    "output_profiles": "transcoder",
    "transcoder_status": "transcoder",
    "error_message": "transcoder",
    "keyframe_interval_ms": "transcoder",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique event identifier (UUID)",
    "event_type": "Event type (cdn_miss/hls_dash_fetch/health_check/transcoder_event)",
    "timestamp": "Event timestamp in ISO 8601 format",
    "origin_host": "Origin server hostname",
    "request_method": "HTTP method of the origin request",
    "request_uri": "Requested URI path on origin",
    "http_protocol": "HTTP protocol version",
    "cdn_pop": "CDN edge node that sent the origin request",
    "medianova_req_id": "Correlation key linking to Medianova CDN request",
    "status_code": "HTTP response status code from origin",
    "response_time_ms": "Origin response time in milliseconds",
    "bytes_sent": "Response body size in bytes",
    "cache_control_header": "Cache-Control header value set by origin",
    "origin_load_pct": "Current origin server CPU load percentage (0-100)",
    "channel": "Streaming channel identifier",
    "stream_type": "Content stream type (live/vod)",
    "manifest_type": "Manifest format (hls_master/hls_media/dash_mpd/segment)",
    "segment_number": "HLS/DASH segment sequence number",
    "bitrate_kbps": "Stream bitrate in kbps",
    "duration_ms": "Segment duration in milliseconds",
    "health_status": "Origin health status (healthy/degraded/unhealthy)",
    "check_source": "Health check initiator (medianova/internal)",
    "latency_ms": "Health check response latency in milliseconds",
    "encoder_id": "Transcoder encoder identifier",
    "input_stream": "Input stream source for transcoder",
    "output_profiles": "List of output encoding profiles",
    "transcoder_status": "Transcoder state (started/running/error/stopped)",
    "error_message": "Error description for failed transcoder events",
    "keyframe_interval_ms": "Keyframe interval in milliseconds",
}
