"""Schema Registry — all queryable tables and columns for NL→SQL."""

from __future__ import annotations

QUERYABLE_TABLES: dict[str, dict] = {
    # ── shared_analytics (analytics.duckdb) ──
    "shared_analytics.incidents": {
        "description": "Platform incidents and alerts",
        "columns": ["incident_id", "tenant_id", "severity", "title", "status", "source_app",
                     "created_at", "updated_at", "resolved_at", "mttr_seconds"],
        "pii_columns": [],
        "db": "analytics",
    },
    "shared_analytics.qoe_metrics": {
        "description": "Quality of Experience session metrics",
        "columns": ["session_id", "tenant_id", "quality_score", "buffering_ratio",
                     "startup_time_ms", "bitrate_avg", "device_type", "created_at"],
        "pii_columns": [],
        "db": "analytics",
    },
    "shared_analytics.cdn_analysis": {
        "description": "CDN performance analysis results",
        "columns": ["analysis_id", "tenant_id", "error_rate", "cache_hit_rate",
                     "total_requests", "avg_ttfb_ms", "created_at"],
        "pii_columns": [],
        "db": "analytics",
    },
    "shared_analytics.live_events": {
        "description": "Live event catalog and status",
        "columns": ["event_id", "tenant_id", "event_name", "sport", "competition",
                     "kickoff_time", "status", "expected_viewers", "created_at"],
        "pii_columns": [],
        "db": "analytics",
    },
    "shared_analytics.agent_decisions": {
        "description": "AI agent decisions and actions",
        "columns": ["decision_id", "tenant_id", "app", "action", "risk_level",
                     "approval_required", "llm_model_used", "created_at"],
        "pii_columns": [],
        "db": "analytics",
    },
    "shared_analytics.alerts_sent": {
        "description": "Alerts sent via routing pipeline",
        "columns": ["alert_id", "tenant_id", "source_app", "severity", "channel",
                     "title", "status", "sent_at"],
        "pii_columns": [],
        "db": "analytics",
    },
    # ── logs.duckdb (schema = tenant's duckdb_schema) ──
    "{schema}.medianova_logs": {
        "description": "Medianova CDN access logs",
        "columns": ["timestamp", "tenant_id", "edge_server", "bytes_sent", "status_code",
                     "cache_status", "cache_hit", "content_id", "content_type",
                     "country_code", "isp", "device_type", "protocol", "response_time_ms"],
        "pii_columns": ["client_ip"],
        "db": "logs",
    },
    "{schema}.player_events_logs": {
        "description": "Player session events (play, buffer, error)",
        "columns": ["timestamp", "tenant_id", "event_type", "session_id", "content_id",
                     "device_type", "qoe_score", "bitrate_kbps", "buffer_ratio", "country_code"],
        "pii_columns": ["subscriber_id"],
        "db": "logs",
    },
    "{schema}.api_logs_logs": {
        "description": "API gateway request logs",
        "columns": ["timestamp", "tenant_id", "endpoint", "method", "status_code",
                     "device_type", "response_time_ms", "error_code", "country_code"],
        "pii_columns": ["subscriber_id"],
        "db": "logs",
    },
    "{schema}.npaw_analytics_logs": {
        "description": "NPAW/Youbora video analytics",
        "columns": ["timestamp", "tenant_id", "session_id", "content_id", "qoe_score",
                     "youbora_score", "rebuffering_ratio", "bitrate_avg", "device_type"],
        "pii_columns": ["subscriber_id"],
        "db": "logs",
    },
    "{schema}.newrelic_apm_logs": {
        "description": "New Relic APM infrastructure metrics",
        "columns": ["timestamp", "tenant_id", "event_type", "service_name", "apdex_score",
                     "error_rate", "throughput", "response_time_ms", "cpu_pct"],
        "pii_columns": [],
        "db": "logs",
    },
    "{schema}.crm_subscriber_logs": {
        "description": "CRM subscriber data",
        "columns": ["timestamp", "tenant_id", "subscription_tier", "churn_risk",
                     "lifetime_value", "country_code", "device_type"],
        "pii_columns": ["subscriber_id"],
        "db": "logs",
    },
    "{schema}.billing_logs": {
        "description": "Billing and payment events",
        "columns": ["timestamp", "tenant_id", "event_type", "amount", "currency",
                     "payment_status", "subscription_tier"],
        "pii_columns": ["subscriber_id"],
        "db": "logs",
    },
    "{schema}.epg_logs": {
        "description": "Electronic Program Guide schedule",
        "columns": ["timestamp", "tenant_id", "channel", "content_id", "title",
                     "event_type", "expected_viewers", "pre_scale_required"],
        "pii_columns": [],
        "db": "logs",
    },
}


def get_schema_context(schema: str) -> str:
    """Generate LLM context string from registry."""
    lines = ["Available tables:\n"]
    for table_key, meta in QUERYABLE_TABLES.items():
        table = table_key.replace("{schema}", schema)
        safe_cols = [c for c in meta["columns"] if c not in meta.get("pii_columns", [])]
        lines.append(f"  {table}: {meta['description']}")
        lines.append(f"    Columns: {', '.join(safe_cols)}")
    return "\n".join(lines)


def get_all_pii_columns() -> set[str]:
    """Return all PII column names across all tables."""
    pii = set()
    for meta in QUERYABLE_TABLES.values():
        pii.update(meta.get("pii_columns", []))
    return pii


def get_table_list(schema: str) -> list[dict]:
    """Return table list for GET /nl-query/tables."""
    result = []
    for table_key, meta in QUERYABLE_TABLES.items():
        table = table_key.replace("{schema}", schema)
        safe_cols = [c for c in meta["columns"] if c not in meta.get("pii_columns", [])]
        result.append({
            "table": table,
            "description": meta["description"],
            "columns": safe_cols,
            "db": meta["db"],
        })
    return result
