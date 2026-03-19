"""Akamai DataStream 2 schemas — log entries, config, metrics, anomalies."""

from __future__ import annotations

from pydantic import BaseModel


class AkamaiLogEntry(BaseModel):
    req_time_sec: float | None = None
    cp: str | None = None
    bytes: int | None = None
    cli_ip_hash: str | None = None
    status_code: int | None = None
    proto: str | None = None
    req_host: str | None = None
    req_path: str | None = None
    ua_hash: str | None = None
    referer: str | None = None
    tls_version: str | None = None
    tls_oh: str | None = None
    headers_cnt: int | None = None
    headers_size: int | None = None
    body_size: int | None = None
    cacheable: bool | None = None
    cache_status: str | None = None
    error_code: str | None = None
    edge_ip: str | None = None
    country: str | None = None
    city: str | None = None


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
    protocol_breakdown: dict = {}
    tls_breakdown: dict = {}
    peak_hours: list[dict] = []


class AkamaiAnomaly(BaseModel):
    anomaly_type: str
    severity: str
    value: float
    threshold: float
    description: str
