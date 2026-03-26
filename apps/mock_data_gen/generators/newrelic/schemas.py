"""New Relic APM schema — 3 event types: apm_transaction, infrastructure, error_event."""

from __future__ import annotations

from pydantic import BaseModel


class NewRelicAPMEntry(BaseModel):
    """New Relic APM monitoring entry — 3 event types."""

    # ── META ──
    event_id: str
    event_type: str  # apm_transaction | infrastructure | error_event
    timestamp: str  # ISO 8601

    # ── APM TRANSACTION ──
    service_name: str | None = None
    transaction_name: str | None = None
    duration_ms: float | None = None
    error_rate: float | None = None  # 0.0-1.0
    throughput_rpm: int | None = None
    apdex_score: float | None = None  # 0.0-1.0
    slow_query_count: int | None = None

    # ── INFRASTRUCTURE ──
    host: str | None = None
    cpu_pct: float | None = None
    memory_pct: float | None = None
    disk_io_mbps: float | None = None
    network_mbps: float | None = None
    pod_count: int | None = None

    # ── ERROR EVENT ──
    error_class: str | None = None
    error_message: str | None = None
    stack_trace_hash: str | None = None  # SHA256
    impacted_users: int | None = None


FIELD_CATEGORIES: dict[str, str] = {
    "event_id": "meta",
    "event_type": "meta",
    "timestamp": "meta",
    "service_name": "apm",
    "transaction_name": "apm",
    "duration_ms": "apm",
    "error_rate": "apm",
    "throughput_rpm": "apm",
    "apdex_score": "apm",
    "slow_query_count": "apm",
    "host": "infrastructure",
    "cpu_pct": "infrastructure",
    "memory_pct": "infrastructure",
    "disk_io_mbps": "infrastructure",
    "network_mbps": "infrastructure",
    "pod_count": "infrastructure",
    "error_class": "error",
    "error_message": "error",
    "stack_trace_hash": "error",
    "impacted_users": "error",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "event_id": "Unique event identifier (UUID)",
    "event_type": "Event type (apm_transaction/infrastructure/error_event)",
    "timestamp": "Event timestamp in ISO 8601 format",
    "service_name": "Microservice name (api-gateway/drm-service/stream-packager/auth-service/subscription-service)",
    "transaction_name": "Transaction/endpoint name being monitored",
    "duration_ms": "Average transaction duration in milliseconds",
    "error_rate": "Error rate for the time window (0.0-1.0)",
    "throughput_rpm": "Requests per minute throughput",
    "apdex_score": "Application Performance Index score (0.0-1.0)",
    "slow_query_count": "Number of slow database queries in the time window",
    "host": "Kubernetes pod/host identifier",
    "cpu_pct": "CPU utilization percentage (0-100)",
    "memory_pct": "Memory utilization percentage (0-100)",
    "disk_io_mbps": "Disk I/O throughput in MB/s",
    "network_mbps": "Network throughput in MB/s",
    "pod_count": "Number of active pods for the service",
    "error_class": "Exception class name",
    "error_message": "Error description",
    "stack_trace_hash": "Stack trace fingerprint (SHA256 hashed)",
    "impacted_users": "Estimated number of users affected by the error",
}
