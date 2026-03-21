"""Akamai DataStream 2 schemas — 22-field log entries, config, metrics, anomalies."""

from __future__ import annotations

from pydantic import BaseModel


class AkamaiLogEntry(BaseModel):
    """22-field Akamai DataStream 2 log entry (TSV format)."""

    # Meta
    version: int | None = None                # field 00
    cp_code: str | None = None                # field 01 — cpCode
    # Timing
    req_time_sec: float | None = None         # field 02 — Unix epoch
    dns_lookup_time_ms: int | None = None     # field 14
    transfer_time_ms: int | None = None       # field 15
    turn_around_time_ms: int | None = None    # field 16
    # Traffic
    bytes: int | None = None                  # field 03
    client_bytes: int | None = None           # field 04
    response_body_size: int | None = None     # field 06
    # Content
    content_type: str | None = None           # field 05
    req_path: str | None = None               # field 09
    # Client
    user_agent: str | None = None             # field 07 — PII: hash before LLM
    client_ip: str | None = None              # field 11 — PII: hash before storage
    req_range: str | None = None              # field 12
    # Network
    hostname: str | None = None               # field 08
    edge_ip: str | None = None                # field 19
    # Response
    status_code: int | None = None            # field 10
    error_code: str | None = None             # field 17
    # Cache
    cache_status: int | None = None           # field 13 — 0/1/2/3
    cache_hit: int | None = None              # field 18 — 0/1
    # Geo
    country: str | None = None                # field 20
    city: str | None = None                   # field 21


# ── Backward-compat aliases for old field names used in tests ──
# These allow existing tests using .cli_ip_hash, .proto, .ua_hash etc. to keep working
# by mapping to new fields in the parse layer.


class AkamaiConfig(BaseModel):
    s3_bucket: str
    s3_prefix: str
    tenant_id: str
    project_id: str


class AkamaiMetrics(BaseModel):
    total_requests: int = 0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    avg_ttfb_ms: float = 0.0
    p99_ttfb_ms: float = 0.0
    total_bytes: int = 0
    top_errors: list[dict] = []
    edge_breakdown: list[dict] = []
    geo_breakdown: list[dict] = []
    status_breakdown: dict = {}
    content_type_breakdown: dict = {}
    city_breakdown: list[dict] = []
    peak_hours: list[dict] = []


class AkamaiAnomaly(BaseModel):
    anomaly_type: str
    severity: str
    value: float
    threshold: float
    description: str
