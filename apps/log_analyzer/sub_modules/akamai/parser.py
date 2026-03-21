"""Akamai DataStream 2 log parser — TSV (22 fields) and CSV/JSON with PII scrubbing."""

from __future__ import annotations

import csv
import hashlib
import io
import json

import structlog

from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry

logger = structlog.get_logger(__name__)

# DS2 TSV field order (22 fields, tab-separated)
TSV_FIELD_ORDER = [
    "version", "cp_code", "req_time_sec", "bytes", "client_bytes",
    "content_type", "response_body_size", "user_agent", "hostname",
    "req_path", "status_code", "client_ip", "req_range", "cache_status",
    "dns_lookup_time_ms", "transfer_time_ms", "turn_around_time_ms",
    "error_code", "cache_hit", "edge_ip", "country", "city",
]

# CSV header → AkamaiLogEntry field mapping (backward compat with old CSV format)
CSV_FIELD_MAP: dict[str, str] = {
    "reqTimeSec": "req_time_sec",
    "CP": "cp_code",
    "Bytes": "bytes",
    "cliIP": "client_ip",
    "statusCode": "status_code",
    "proto": "_proto",
    "reqHost": "hostname",
    "reqPath": "req_path",
    "UA": "user_agent",
    "referer": "_referer",
    "tlsVersion": "_tls_version",
    "tlsOH": "_tls_oh",
    "headersCnt": "_headers_cnt",
    "headersSize": "_headers_size",
    "bodySize": "response_body_size",
    "cacheable": "_cacheable",
    "cacheStatus": "_cache_status_str",
    "errorCode": "error_code",
    "edgeIP": "edge_ip",
    "country": "country",
    "city": "city",
    # New DS2 fields in CSV format
    "version": "version",
    "clientBytes": "client_bytes",
    "contentType": "content_type",
    "reqRange": "req_range",
    "dnsLookupTimeMSec": "dns_lookup_time_ms",
    "transferTimeMSec": "transfer_time_ms",
    "turnAroundTimeMSec": "turn_around_time_ms",
    "cacheHit": "cache_hit",
}

# PII fields that need hashing
_PII_FIELDS = {"cliIP", "UA", "client_ip", "user_agent"}

_INT_FIELDS = {
    "bytes", "status_code", "response_body_size", "dns_lookup_time_ms",
    "transfer_time_ms", "turn_around_time_ms", "cache_status", "cache_hit",
    "version", "client_bytes", "_headers_cnt", "_headers_size",
}
_FLOAT_FIELDS = {"req_time_sec"}


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


def _build_entry(raw: dict[str, str]) -> AkamaiLogEntry:
    """Convert a raw row dict into an AkamaiLogEntry with PII scrubbing."""
    mapped: dict[str, object] = {}
    for csv_key, field_name in CSV_FIELD_MAP.items():
        val = raw.get(csv_key, "").strip()
        if not val:
            continue

        # Skip internal fields (prefixed with _)
        if field_name.startswith("_"):
            if field_name == "_cache_status_str":
                mapped["cache_status"] = 1 if val.upper() == "HIT" else 0
            continue

        # PII scrub
        if csv_key in _PII_FIELDS:
            mapped[field_name] = _hash_value(val)
        elif field_name in _INT_FIELDS:
            mapped[field_name] = _coerce_int(val)
        elif field_name in _FLOAT_FIELDS:
            mapped[field_name] = _coerce_float(val)
        else:
            mapped[field_name] = val

    return AkamaiLogEntry(**mapped)


def parse_tsv(content: str) -> list[AkamaiLogEntry]:
    """Parse Akamai DataStream 2 TSV content (22 tab-separated fields per line)."""
    entries: list[AkamaiLogEntry] = []
    for i, line in enumerate(content.strip().splitlines()):
        fields = line.split("\t")
        if len(fields) < 22:
            logger.warning("akamai_tsv_short_line", row=i, fields=len(fields))
            fields.extend([""] * (22 - len(fields)))
        raw = dict(zip(TSV_FIELD_ORDER, fields[:22], strict=False))
        try:
            if raw.get("client_ip"):
                raw["client_ip"] = _hash_value(raw["client_ip"])
            if raw.get("user_agent"):
                raw["user_agent"] = _hash_value(raw["user_agent"])
            entry_data: dict[str, object] = {}
            for k, v in raw.items():
                v = v.strip()
                if not v:
                    continue
                if k in _INT_FIELDS:
                    entry_data[k] = _coerce_int(v)
                elif k in _FLOAT_FIELDS:
                    entry_data[k] = _coerce_float(v)
                else:
                    entry_data[k] = v
            entries.append(AkamaiLogEntry(**entry_data))
        except Exception:
            logger.warning("akamai_tsv_row_error", row=i)
    return entries


def parse_csv(content: str) -> list[AkamaiLogEntry]:
    """Parse Akamai DataStream 2 CSV content (header row + data)."""
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
    first_line = content.split("\n")[0] if content else ""
    if "\t" in first_line and "," not in first_line:
        return parse_tsv(content)
    return parse_csv(content)
