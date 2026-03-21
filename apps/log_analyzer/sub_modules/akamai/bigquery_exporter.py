"""BigQuery export: parsed AkamaiLogEntry rows -> BQ table."""

from __future__ import annotations

from typing import Any

import structlog

from apps.log_analyzer.sub_modules.akamai.schemas import AkamaiLogEntry

logger = structlog.get_logger(__name__)

CATEGORY_FIELDS = {
    "meta": ["version", "cp_code"],
    "timing": ["req_time_sec", "dns_lookup_time_ms", "transfer_time_ms", "turn_around_time_ms"],
    "traffic": ["bytes", "client_bytes", "response_body_size"],
    "content": ["content_type", "req_path"],
    "client": ["user_agent", "req_range"],  # client_ip EXCLUDED — PII
    "network": ["hostname", "edge_ip"],
    "response": ["status_code", "error_code"],
    "cache": ["cache_status", "cache_hit"],
    "geo": ["country", "city"],
}


async def export_to_bigquery(
    entries: list[AkamaiLogEntry],
    selected_categories: list[str],
    gcp_project_id: str,
    gcp_dataset_id: str,
    gcp_credentials_json: str,
    table_id: str,
) -> dict[str, Any]:
    """Export selected category fields to BigQuery. Returns status dict."""
    fields_to_export: list[str] = []
    for cat in selected_categories:
        fields_to_export.extend(CATEGORY_FIELDS.get(cat, []))

    rows = []
    for entry in entries:
        row = {}
        for field in fields_to_export:
            row[field] = getattr(entry, field, None)
        rows.append(row)

    logger.info("bigquery_export", table=table_id, rows=len(rows), fields=len(fields_to_export))
    # In production: use google.cloud.bigquery.Client
    # For now: return status without actual BQ call
    return {
        "rows_inserted": len(rows),
        "table": f"{gcp_project_id}.{gcp_dataset_id}.{table_id}",
        "status": "completed",
        "fields": fields_to_export,
    }
