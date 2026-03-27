"""JSONL.gz parser — reads compressed log files and maps to DuckDB schema."""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Mapping from source schema field names to DuckDB column names.
# Only fields present in log_schemas.py are included; others are dropped.
_FIELD_MAPS: dict[str, dict[str, str]] = {
    "medianova": {
        "timestamp": "timestamp", "edge_node": "edge_server",
        "remote_addr": "client_ip", "bytes_sent": "bytes_sent",
        "status": "status_code", "proxy_cache_status": "cache_status",
        "content_type": "content_type", "country_code": "country_code",
        "isp": "isp", "stream_type": "device_type",
        "http_protocol": "protocol", "request_time": "response_time_ms",
    },
    "origin_server": {
        "timestamp": "timestamp", "event_type": "event_type",
        "cdn_pop": "edge_server", "status_code": "status_code",
        "response_time_ms": "response_time_ms", "bytes_sent": "bytes_sent",
        "error_code": "error_code",
    },
    "widevine_drm": {
        "timestamp": "timestamp", "event_type": "event_type",
        "device_type": "device_type", "session_id": "session_id",
        "drm_server": "drm_server", "error_code": "error_code",
        "status": "status", "response_time_ms": "response_time_ms",
        "country_code": "country_code", "subscription_tier": "subscription_tier",
    },
    "fairplay_drm": {
        "timestamp": "timestamp", "event_type": "event_type",
        "device_type": "device_type", "certificate_status": "certificate_status",
        "error_code": "error_code", "status": "status",
        "response_time_ms": "response_time_ms", "country_code": "country_code",
        "ios_version": "ios_version",
    },
    "player_events": {
        "timestamp": "timestamp", "event_type": "event_type",
        "session_id": "session_id", "device_type": "device_type",
        "error_code": "error_code", "buffer_ratio": "buffer_ratio",
        "country_code": "country_code",
    },
    "npaw_analytics": {
        "timestamp": "timestamp", "session_id": "session_id",
        "qoe_score": "qoe_score", "youbora_score": "youbora_score",
        "rebuffering_ratio": "rebuffering_ratio",
        "avg_bitrate_kbps": "bitrate_avg", "device_type": "device_type",
    },
    "api_logs": {
        "timestamp": "timestamp", "endpoint": "endpoint",
        "method": "method", "status_code": "status_code",
        "device_type": "device_type", "response_time_ms": "response_time_ms",
        "error_code": "error_code", "country_code": "country_code",
    },
    "newrelic_apm": {
        "timestamp": "timestamp", "event_type": "event_type",
        "service_name": "service_name", "apdex_score": "apdex_score",
        "error_rate": "error_rate", "throughput_rpm": "throughput",
        "cpu_pct": "cpu_pct",
    },
    "crm_subscriber": {
        "timestamp": "timestamp", "subscription_tier": "subscription_tier",
        "churn_risk_score": "churn_risk", "country_code": "country_code",
        "device_type": "device_type",
    },
    "epg": {
        "start_time": "timestamp", "channel_id": "channel",
        "title": "title", "category": "event_type",
        "expected_viewers": "expected_viewers",
        "pre_scale_required": "pre_scale_required",
    },
    "billing": {
        "timestamp": "timestamp", "event_type": "event_type",
        "amount_tl": "amount", "currency": "currency",
        "status": "payment_status", "subscription_tier": "subscription_tier",
    },
    "push_notifications": {
        "timestamp": "timestamp", "notification_type": "notification_type",
        "title": "title", "delivered": "delivery_status",
    },
    "app_reviews": {
        "timestamp": "timestamp", "platform": "platform",
        "rating": "rating", "sentiment": "sentiment",
        "category": "category", "device_model": "device_type",
        "app_version": "app_version", "country": "country_code",
    },
}


def parse_jsonl_gz(file_path: str, source_name: str, tenant_id: str) -> list[dict]:
    """Parse a .jsonl.gz file and map fields to DuckDB schema."""
    field_map = _FIELD_MAPS.get(source_name, {})
    now = datetime.now(timezone.utc).isoformat()
    records: list[dict] = []

    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("jsonl_parse_error", file=file_path, line=line_num)
                    continue

                mapped: dict = {"tenant_id": tenant_id, "ingested_at": now}
                for src_field, dst_field in field_map.items():
                    if src_field in raw:
                        mapped[dst_field] = raw[src_field]
                records.append(mapped)
    except FileNotFoundError:
        logger.warning("file_not_found", file=file_path)
    except Exception as exc:
        logger.warning("jsonl_parse_exception", file=file_path, error=str(exc))

    return records


def parse_json_file(file_path: str, source_name: str, tenant_id: str) -> list[dict]:
    """Parse a plain .json file (used by EPG and App Reviews)."""
    field_map = _FIELD_MAPS.get(source_name, {})
    now = datetime.now(timezone.utc).isoformat()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("json_parse_error", file=file_path, error=str(exc))
        return []

    items = data if isinstance(data, list) else [data]
    records: list[dict] = []
    for raw in items:
        mapped: dict = {"tenant_id": tenant_id, "ingested_at": now}
        for src_field, dst_field in field_map.items():
            if src_field in raw:
                mapped[dst_field] = raw[src_field]
        records.append(mapped)

    return records


def scan_source_directory(base_path: str, source_name: str) -> list[str]:
    """Walk directory recursively, return all .jsonl.gz and .json files sorted."""
    if not os.path.exists(base_path):
        return []

    files: list[str] = []
    for root, _dirs, filenames in os.walk(base_path):
        for fn in filenames:
            if fn.endswith(".jsonl.gz") or fn.endswith(".json"):
                files.append(os.path.join(root, fn))

    files.sort()
    return files
