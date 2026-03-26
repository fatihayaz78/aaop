"""Medianova CDN log schema — 32 fields, 8 categories."""

from __future__ import annotations

from pydantic import BaseModel


class MedianovaLogEntry(BaseModel):
    """Medianova CDN access log entry — 32 fields across 8 categories."""

    # ── REQUEST DETAILS (10) ──
    request_id: str
    request_method: str  # GET | HEAD | POST
    request_uri: str
    request_param: str | None = None
    request_time: float  # seconds
    scheme: str  # https | http
    http_protocol: str  # HTTP/1.1 | HTTP/2.0
    http_host: str
    http_referrer: str | None = None
    http_user_agent: str

    # ── RESPONSE & CACHING (8) ──
    status: int  # 200 | 206 | 304 | 404 | 500 | 502 | 503
    content_type: str
    proxy_cache_status: str  # HIT | MISS | BYPASS | EXPIRED | STALE
    body_bytes_sent: int
    bytes_sent: int
    upstream_response_time: float | None = None  # null on HIT
    sent_http_content_length: int | None = None
    via: str | None = None

    # ── CLIENT & NETWORK (8) ──
    timestamp: str  # ISO 8601
    remote_addr: str  # SHA256 hashed
    client_port: int
    asn: str
    country_code: str
    isp: str
    tcp_info_rtt: int  # ms
    tcp_info_rtt_var: int  # ms

    # ── SECURITY & SSL (4) ──
    ssl_protocol: str | None = None  # TLSv1.2 | TLSv1.3
    ssl_cipher: str | None = None
    resource_uuid: str
    account_type: str  # enterprise | standard

    # ── AAOP EXTENSIONS (3) ──
    channel: str
    edge_node: str  # ist-01 | ist-02 | ank-01 | izm-01 | fra-01
    stream_type: str  # live | vod | hls_segment | manifest


FIELD_CATEGORIES: dict[str, str] = {
    # Request Details
    "request_id": "request",
    "request_method": "request",
    "request_uri": "request",
    "request_param": "request",
    "request_time": "request",
    "scheme": "request",
    "http_protocol": "request",
    "http_host": "request",
    "http_referrer": "request",
    "http_user_agent": "request",
    # Response & Caching
    "status": "response",
    "content_type": "response",
    "proxy_cache_status": "response",
    "body_bytes_sent": "response",
    "bytes_sent": "response",
    "upstream_response_time": "response",
    "sent_http_content_length": "response",
    "via": "response",
    # Client & Network
    "timestamp": "client",
    "remote_addr": "client",
    "client_port": "client",
    "asn": "network",
    "country_code": "network",
    "isp": "network",
    "tcp_info_rtt": "network",
    "tcp_info_rtt_var": "network",
    # Security & SSL
    "ssl_protocol": "security",
    "ssl_cipher": "security",
    "resource_uuid": "security",
    "account_type": "security",
    # AAOP Extensions
    "channel": "aaop",
    "edge_node": "aaop",
    "stream_type": "aaop",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "request_id": "Unique request identifier (UUID)",
    "request_method": "HTTP method (GET, HEAD, POST)",
    "request_uri": "Requested URI path",
    "request_param": "Query string parameters",
    "request_time": "Total request processing time in seconds",
    "scheme": "Protocol scheme (http/https)",
    "http_protocol": "HTTP protocol version",
    "http_host": "Host header value",
    "http_referrer": "Referer header value",
    "http_user_agent": "Client user agent string",
    "status": "HTTP response status code",
    "content_type": "Response content MIME type",
    "proxy_cache_status": "CDN cache status (HIT/MISS/BYPASS/EXPIRED/STALE)",
    "body_bytes_sent": "Response body size in bytes",
    "bytes_sent": "Total bytes sent including headers",
    "upstream_response_time": "Origin response time in seconds (null on cache HIT)",
    "sent_http_content_length": "Content-Length header value",
    "via": "Via header indicating proxy chain",
    "timestamp": "Request timestamp in ISO 8601 format",
    "remote_addr": "Client IP address (SHA256 hashed)",
    "client_port": "Client source port number",
    "asn": "Autonomous System Number of the client",
    "country_code": "Client country code (ISO 3166-1 alpha-2)",
    "isp": "Client Internet Service Provider name",
    "tcp_info_rtt": "TCP round-trip time in milliseconds",
    "tcp_info_rtt_var": "TCP RTT variance in milliseconds",
    "ssl_protocol": "TLS protocol version (TLSv1.2/TLSv1.3)",
    "ssl_cipher": "TLS cipher suite used",
    "resource_uuid": "Unique resource identifier",
    "account_type": "CDN account type (enterprise/standard)",
    "channel": "Streaming channel identifier",
    "edge_node": "CDN edge server location",
    "stream_type": "Content stream type (live/vod/hls_segment/manifest)",
}
