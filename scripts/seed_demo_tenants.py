"""Seed demo tenant data into logs.duckdb — tv_plus, music_stream, fly_ent.

Uses DuckDB's generate_series + range functions for fast bulk generation.
Idempotent: drops and recreates data. Does NOT touch sport_stream or aaop_company.

Usage:
    source ~/.venvs/aaop/bin/activate
    python scripts/seed_demo_tenants.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import duckdb

LOGS_DB = "./data/duckdb/logs.duckdb"
NOW = datetime.now(timezone.utc)

# ── Schema DDLs (same columns as sport_stream) ──────────────────

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS {S}.api_logs_logs (
    timestamp TIMESTAMP, tenant_id VARCHAR, endpoint VARCHAR, method VARCHAR,
    status_code INTEGER, subscriber_id VARCHAR, device_type VARCHAR,
    response_time_ms INTEGER, error_code VARCHAR, country_code VARCHAR, ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {S}.player_events_logs (
    timestamp TIMESTAMP, tenant_id VARCHAR, event_type VARCHAR, session_id VARCHAR,
    subscriber_id VARCHAR, content_id VARCHAR, device_type VARCHAR, qoe_score FLOAT,
    error_code VARCHAR, bitrate_kbps INTEGER, buffer_ratio FLOAT, country_code VARCHAR,
    ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {S}.billing_logs (
    timestamp TIMESTAMP, tenant_id VARCHAR, event_type VARCHAR, subscriber_id VARCHAR,
    amount FLOAT, currency VARCHAR, payment_status VARCHAR, subscription_tier VARCHAR,
    ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {S}.crm_subscriber_logs (
    timestamp TIMESTAMP, tenant_id VARCHAR, subscriber_id VARCHAR, subscription_tier VARCHAR,
    churn_risk FLOAT, lifetime_value FLOAT, country_code VARCHAR, device_type VARCHAR,
    ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS {S}.newrelic_apm_logs (
    timestamp TIMESTAMP, tenant_id VARCHAR, event_type VARCHAR, service_name VARCHAR,
    apdex_score FLOAT, error_rate FLOAT, throughput FLOAT, response_time_ms FLOAT,
    cpu_pct FLOAT, memory_mb FLOAT, ingested_at TIMESTAMP);
"""


def setup_schema(conn: duckdb.DuckDBPyConnection, schema: str) -> None:
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for stmt in TABLES_SQL.replace("{S}", schema).split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    # Clear existing data for idempotent re-run
    tables = conn.execute(
        f"SELECT table_name FROM information_schema.tables WHERE table_schema='{schema}'"
    ).fetchall()
    for (t,) in tables:
        conn.execute(f"DELETE FROM {schema}.{t}")


def seed_via_sql(conn: duckdb.DuckDBPyConnection, schema: str, tenant_id: str,
                 config: dict) -> int:
    """Generate data using DuckDB SQL — orders of magnitude faster than Python loops."""
    total = 0

    api_count = config["api_per_day"]
    player_count = config["player_per_day"]
    billing_count = config.get("billing_per_day", 0)
    crm_count = config.get("crm_per_day", 0)
    apm_count = config.get("apm_per_day", 0)
    endpoints = config["endpoints"]
    events = config["events"]
    contents = config["contents"]
    tiers = config["tiers"]

    endpoints_list = "'" + "','".join(endpoints) + "'"
    events_list = "'" + "','".join(events) + "'"
    contents_list = "'" + "','".join(contents) + "'"
    tiers_list = "'" + "','".join(tiers) + "'"
    devices = "'mobile_android','mobile_ios','smart_tv','web','stb'"
    countries = "'TR','DE','UK','US','NL','FR'"
    methods = "'GET','POST','PUT','DELETE'"
    statuses = "200,200,200,200,200,200,200,201,301,400,401,404,500,502,503"

    # API logs
    if api_count > 0:
        conn.execute(f"""
            INSERT INTO {schema}.api_logs_logs
            SELECT
                CURRENT_DATE - INTERVAL (floor(random()*28)::INT) DAY
                    + INTERVAL (floor(random()*24)::INT) HOUR
                    + INTERVAL (floor(random()*60)::INT) MINUTE
                    + INTERVAL (floor(random()*60)::INT) SECOND AS timestamp,
                '{tenant_id}' AS tenant_id,
                (ARRAY[{endpoints_list}])[1 + floor(random()*{len(endpoints)})::INT] AS endpoint,
                (ARRAY[{methods}])[1 + floor(random()*4)::INT] AS method,
                (ARRAY[{statuses}])[1 + floor(random()*15)::INT] AS status_code,
                'sub_' || (100000 + floor(random()*900000)::INT)::VARCHAR AS subscriber_id,
                (ARRAY[{devices}])[1 + floor(random()*5)::INT] AS device_type,
                5 + floor(random()*2000)::INT AS response_time_ms,
                CASE WHEN random() < 0.09 THEN (ARRAY['ERR_TIMEOUT','ERR_503','ERR_CONNECT','ERR_AUTH',''])[1 + floor(random()*5)::INT] ELSE '' END AS error_code,
                (ARRAY[{countries}])[1 + floor(random()*6)::INT] AS country_code,
                CURRENT_TIMESTAMP AS ingested_at
            FROM generate_series(1, {api_count * 28})
        """)
        cnt = conn.execute(f"SELECT COUNT(*) FROM {schema}.api_logs_logs").fetchone()[0]
        total += cnt
        print(f"  {schema}.api_logs_logs: {cnt:,}")

    # Player events
    if player_count > 0:
        conn.execute(f"""
            INSERT INTO {schema}.player_events_logs
            SELECT
                CURRENT_DATE - INTERVAL (floor(random()*28)::INT) DAY
                    + INTERVAL (floor(random()*24)::INT) HOUR
                    + INTERVAL (floor(random()*60)::INT) MINUTE AS timestamp,
                '{tenant_id}' AS tenant_id,
                (ARRAY[{events_list}])[1 + floor(random()*{len(events)})::INT] AS event_type,
                'sess_' || (1 + floor(random()*999999)::INT)::VARCHAR AS session_id,
                'sub_' || (100000 + floor(random()*900000)::INT)::VARCHAR AS subscriber_id,
                (ARRAY[{contents_list}])[1 + floor(random()*{len(contents)})::INT] AS content_id,
                (ARRAY[{devices}])[1 + floor(random()*5)::INT] AS device_type,
                2.0 + random()*3.0 AS qoe_score,
                CASE WHEN random() < 0.05 THEN 'ERR_BUFFER' ELSE '' END AS error_code,
                (ARRAY[1500,2500,4500,6000,8000])[1 + floor(random()*5)::INT] AS bitrate_kbps,
                random()*0.08 AS buffer_ratio,
                (ARRAY[{countries}])[1 + floor(random()*6)::INT] AS country_code,
                CURRENT_TIMESTAMP AS ingested_at
            FROM generate_series(1, {player_count * 28})
        """)
        cnt = conn.execute(f"SELECT COUNT(*) FROM {schema}.player_events_logs").fetchone()[0]
        total += cnt
        print(f"  {schema}.player_events_logs: {cnt:,}")

    # Billing
    if billing_count > 0:
        conn.execute(f"""
            INSERT INTO {schema}.billing_logs
            SELECT
                CURRENT_DATE - INTERVAL (floor(random()*28)::INT) DAY
                    + INTERVAL (floor(random()*24)::INT) HOUR AS timestamp,
                '{tenant_id}' AS tenant_id,
                (ARRAY['payment','renewal','cancel','upgrade'])[1 + floor(random()*4)::INT] AS event_type,
                'sub_' || (100000 + floor(random()*900000)::INT)::VARCHAR AS subscriber_id,
                9.99 + random()*70.0 AS amount,
                'TRY' AS currency,
                (ARRAY['success','success','success','failed','pending'])[1 + floor(random()*5)::INT] AS payment_status,
                (ARRAY[{tiers_list}])[1 + floor(random()*{len(tiers)})::INT] AS subscription_tier,
                CURRENT_TIMESTAMP AS ingested_at
            FROM generate_series(1, {billing_count * 28})
        """)
        cnt = conn.execute(f"SELECT COUNT(*) FROM {schema}.billing_logs").fetchone()[0]
        total += cnt
        print(f"  {schema}.billing_logs: {cnt:,}")

    # CRM
    if crm_count > 0:
        conn.execute(f"""
            INSERT INTO {schema}.crm_subscriber_logs
            SELECT
                CURRENT_DATE - INTERVAL (floor(random()*28)::INT) DAY AS timestamp,
                '{tenant_id}' AS tenant_id,
                'sub_' || (100000 + floor(random()*900000)::INT)::VARCHAR AS subscriber_id,
                (ARRAY[{tiers_list}])[1 + floor(random()*{len(tiers)})::INT] AS subscription_tier,
                random() AS churn_risk,
                10.0 + random()*500.0 AS lifetime_value,
                (ARRAY[{countries}])[1 + floor(random()*6)::INT] AS country_code,
                (ARRAY[{devices}])[1 + floor(random()*5)::INT] AS device_type,
                CURRENT_TIMESTAMP AS ingested_at
            FROM generate_series(1, {crm_count * 28})
        """)
        cnt = conn.execute(f"SELECT COUNT(*) FROM {schema}.crm_subscriber_logs").fetchone()[0]
        total += cnt
        print(f"  {schema}.crm_subscriber_logs: {cnt:,}")

    # APM (newrelic)
    if apm_count > 0:
        conn.execute(f"""
            INSERT INTO {schema}.newrelic_apm_logs
            SELECT
                CURRENT_DATE - INTERVAL (floor(random()*28)::INT) DAY
                    + INTERVAL (floor(random()*24)::INT) HOUR AS timestamp,
                '{tenant_id}' AS tenant_id,
                (ARRAY['transaction','metric','error'])[1 + floor(random()*3)::INT] AS event_type,
                (ARRAY['api-gateway','streaming-server','auth-service','billing-api'])[1 + floor(random()*4)::INT] AS service_name,
                0.7 + random()*0.3 AS apdex_score,
                random()*0.1 AS error_rate,
                100.0 + random()*5000.0 AS throughput,
                10.0 + random()*500.0 AS response_time_ms,
                5.0 + random()*75.0 AS cpu_pct,
                256.0 + random()*3840.0 AS memory_mb,
                CURRENT_TIMESTAMP AS ingested_at
            FROM generate_series(1, {apm_count * 28})
        """)
        cnt = conn.execute(f"SELECT COUNT(*) FROM {schema}.newrelic_apm_logs").fetchone()[0]
        total += cnt
        print(f"  {schema}.newrelic_apm_logs: {cnt:,}")

    return total


def main() -> None:
    print("S-MT-03 — Multi-Tenant Demo Data Seeding")
    print()

    # Fix super_admin tenant_id
    try:
        import asyncio
        import aiosqlite
        async def fix():
            c = await aiosqlite.connect("./data/sqlite/platform.db")
            await c.execute("UPDATE users SET tenant_id = NULL WHERE username = 'admin@captainlogar.demo' AND role = 'super_admin'")
            await c.commit()
            await c.close()
        asyncio.run(fix())
        print("✓ super_admin tenant_id → NULL")
    except Exception as e:
        print(f"⚠ super_admin fix: {e}")

    conn = duckdb.connect(LOGS_DB)

    # tv_plus (~1.5M)
    print("\nSeeding tv_plus (Tel Co — OTT/IPTV)...")
    setup_schema(conn, "tv_plus")
    n1 = seed_via_sql(conn, "tv_plus", "tel_co", {
        "api_per_day": 20000, "player_per_day": 25000,
        "billing_per_day": 1500, "crm_per_day": 2000, "apm_per_day": 500,
        "endpoints": ["/api/channels", "/api/epg", "/api/stream/start", "/api/stream/stop", "/api/user/profile", "/api/search"],
        "events": ["play", "pause", "stop", "buffer", "seek", "error", "quality_change"],
        "contents": ["ch_trt1", "ch_ntv", "ch_sport", "ch_news24", "ch_kids", "ch_movie"],
        "tiers": ["basic", "standard", "premium"],
    })
    print(f"✓ tv_plus: {n1:,} rows total")

    # music_stream (~400K)
    print("\nSeeding music_stream (Tel Co — Müzik)...")
    setup_schema(conn, "music_stream")
    n2 = seed_via_sql(conn, "music_stream", "tel_co", {
        "api_per_day": 7000, "player_per_day": 6000,
        "billing_per_day": 0, "crm_per_day": 1000, "apm_per_day": 0,
        "endpoints": ["/api/tracks/play", "/api/playlists", "/api/search", "/api/user/library", "/api/discover"],
        "events": ["play", "pause", "skip", "complete", "buffer", "offline_sync", "like"],
        "contents": ["tr_00123", "tr_00456", "tr_00789", "tr_01234", "tr_05678"],
        "tiers": ["free", "premium", "family"],
    })
    print(f"✓ music_stream: {n2:,} rows total")

    # fly_ent (~250K)
    print("\nSeeding fly_ent (Airline Co — IFE)...")
    setup_schema(conn, "fly_ent")
    n3 = seed_via_sql(conn, "fly_ent", "airline_co", {
        "api_per_day": 5000, "player_per_day": 3000,
        "billing_per_day": 0, "crm_per_day": 1000, "apm_per_day": 0,
        "endpoints": ["/api/checkin", "/api/booking", "/api/ife/stream", "/api/ife/catalog", "/api/loyalty", "/api/wifi"],
        "events": ["ife_play", "ife_pause", "ife_stop", "wifi_connect", "wifi_disconnect", "checkin", "boarding"],
        "contents": ["ife_001", "ife_002", "ife_003", "ife_004", "ife_005"],
        "tiers": ["economy", "business", "miles_plus"],
    })
    print(f"✓ fly_ent: {n3:,} rows total")

    conn.close()

    print(f"\n{'='*50}")
    print(f"Total new rows: {n1 + n2 + n3:,}")
    print("Done.")


if __name__ == "__main__":
    main()
