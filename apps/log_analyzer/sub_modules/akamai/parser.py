"""Akamai DataStream 2 log parser — CSV and JSON formats with PII scrubbing."""

from __future__ import annotations

import csv
import hashlib
import io
import json

import structlog

from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry

logger = structlog.get_logger(__name__)

# CSV header → AkamaiLogEntry field mapping
CSV_FIELD_MAP: dict[str, str] = {
    "reqTimeSec": "req_time_sec",
    "CP": "cp",
    "Bytes": "bytes",
    "cliIP": "cli_ip_hash",
    "statusCode": "status_code",
    "proto": "proto",
    "reqHost": "req_host",
    "reqPath": "req_path",
    "UA": "ua_hash",
    "referer": "referer",
    "tlsVersion": "tls_version",
    "tlsOH": "tls_oh",
    "headersCnt": "headers_cnt",
    "headersSize": "headers_size",
    "bodySize": "body_size",
    "cacheable": "cacheable",
    "cacheStatus": "cache_status",
    "errorCode": "error_code",
    "edgeIP": "edge_ip",
    "country": "country",
    "city": "city",
}

# PII fields that need hashing
_PII_FIELDS = {"cliIP", "UA"}


def _hash_value(value: str) -> str:
    """SHA256 hash for PII scrubbing."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _coerce_int(val: str) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _coerce_float(val: str) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _coerce_bool(val: str) -> bool | None:
    if val in ("1", "true", "True"):
        return True
    if val in ("0", "false", "False"):
        return False
    return None


_INT_FIELDS = {"bytes", "status_code", "headers_cnt", "headers_size", "body_size"}
_FLOAT_FIELDS = {"req_time_sec"}
_BOOL_FIELDS = {"cacheable"}


def _build_entry(raw: dict[str, str]) -> AkamaiLogEntry:
    """Convert a raw row dict (CSV headers) into an AkamaiLogEntry with PII scrubbing."""
    mapped: dict[str, object] = {}
    for csv_key, field_name in CSV_FIELD_MAP.items():
        val = raw.get(csv_key, "").strip()
        if not val:
            mapped[field_name] = None
            continue

        # PII scrub
        if csv_key in _PII_FIELDS:
            mapped[field_name] = _hash_value(val)
        elif field_name in _INT_FIELDS:
            mapped[field_name] = _coerce_int(val)
        elif field_name in _FLOAT_FIELDS:
            mapped[field_name] = _coerce_float(val)
        elif field_name in _BOOL_FIELDS:
            mapped[field_name] = _coerce_bool(val)
        else:
            mapped[field_name] = val

    return AkamaiLogEntry(**mapped)


def parse_csv(content: str) -> list[AkamaiLogEntry]:
    """Parse Akamai DataStream 2 CSV content."""
    reader = csv.DictReader(io.StringIO(content))
    entries: list[AkamaiLogEntry] = []
    for i, row in enumerate(reader):
        try:
            entries.append(_build_entry(row))
        except Exception:
            logger.warning("akamai_parse_csv_row_error", row_index=i)
    return entries


def parse_json(content: str) -> list[AkamaiLogEntry]:
    """Parse Akamai DataStream 2 JSON content (newline-delimited or array)."""
    entries: list[AkamaiLogEntry] = []
    try:
        data = json.loads(content)
        items = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        # Try newline-delimited JSON
        items = []
        for line in content.strip().splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("akamai_parse_json_line_error")
    for i, item in enumerate(items):
        try:
            entries.append(_build_entry(item))
        except Exception:
            logger.warning("akamai_parse_json_item_error", item_index=i)
    return entries


def parse_auto(content: str) -> list[AkamaiLogEntry]:
    """Auto-detect format and parse."""
    content = content.strip()
    if content.startswith("[") or content.startswith("{"):
        return parse_json(content)
    return parse_csv(content)
