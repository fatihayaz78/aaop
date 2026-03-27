"""DuckDB CREATE TABLE statements for all 13 log sources."""

from __future__ import annotations

LOG_TABLE_SCHEMAS: dict[str, str] = {
    "medianova": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, edge_server TEXT,
            client_ip TEXT, bytes_sent BIGINT, status_code INTEGER, cache_status TEXT,
            cache_hit INTEGER, content_id TEXT, content_type TEXT, country_code TEXT,
            isp TEXT, device_type TEXT, protocol TEXT, error_code TEXT,
            response_time_ms INTEGER, ingested_at TIMESTAMP
        )
    """,
    "origin_server": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            edge_server TEXT, content_id TEXT, status_code INTEGER, response_time_ms INTEGER,
            bytes_sent BIGINT, error_code TEXT, ingested_at TIMESTAMP
        )
    """,
    "widevine_drm": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            subscriber_id TEXT, content_id TEXT, device_type TEXT, session_id TEXT,
            drm_server TEXT, error_code TEXT, status TEXT, response_time_ms INTEGER,
            country_code TEXT, subscription_tier TEXT, ingested_at TIMESTAMP
        )
    """,
    "fairplay_drm": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            subscriber_id TEXT, content_id TEXT, device_type TEXT, certificate_status TEXT,
            error_code TEXT, status TEXT, response_time_ms INTEGER, country_code TEXT,
            ios_version TEXT, ingested_at TIMESTAMP
        )
    """,
    "player_events": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            session_id TEXT, subscriber_id TEXT, content_id TEXT, device_type TEXT,
            qoe_score FLOAT, error_code TEXT, bitrate_kbps INTEGER, buffer_ratio FLOAT,
            country_code TEXT, ingested_at TIMESTAMP
        )
    """,
    "npaw_analytics": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, session_id TEXT,
            subscriber_id TEXT, content_id TEXT, qoe_score FLOAT, youbora_score FLOAT,
            rebuffering_ratio FLOAT, bitrate_avg INTEGER, device_type TEXT, ingested_at TIMESTAMP
        )
    """,
    "api_logs": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, endpoint TEXT,
            method TEXT, status_code INTEGER, subscriber_id TEXT, device_type TEXT,
            response_time_ms INTEGER, error_code TEXT, country_code TEXT, ingested_at TIMESTAMP
        )
    """,
    "newrelic_apm": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            service_name TEXT, apdex_score FLOAT, error_rate FLOAT, throughput FLOAT,
            response_time_ms FLOAT, cpu_pct FLOAT, memory_mb FLOAT, ingested_at TIMESTAMP
        )
    """,
    "crm_subscriber": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, subscriber_id TEXT,
            subscription_tier TEXT, churn_risk FLOAT, lifetime_value FLOAT,
            country_code TEXT, device_type TEXT, ingested_at TIMESTAMP
        )
    """,
    "epg": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, channel TEXT,
            content_id TEXT, title TEXT, event_type TEXT,
            expected_viewers INTEGER, pre_scale_required INTEGER, ingested_at TIMESTAMP
        )
    """,
    "billing": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, event_type TEXT,
            subscriber_id TEXT, amount FLOAT, currency TEXT, payment_status TEXT,
            subscription_tier TEXT, ingested_at TIMESTAMP
        )
    """,
    "push_notifications": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT,
            notification_type TEXT, subscriber_id TEXT, title TEXT,
            open_rate FLOAT, delivery_status TEXT, ingested_at TIMESTAMP
        )
    """,
    "app_reviews": """
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TIMESTAMP, tenant_id TEXT, platform TEXT,
            rating INTEGER, sentiment TEXT, category TEXT, device_type TEXT,
            app_version TEXT, country_code TEXT, ingested_at TIMESTAMP
        )
    """,
}
