"""S-DATA-FIX-01 — Fix medianova ingest + CRM timestamp NULLs.

Uses DuckDB's native read_json for fast bulk ingest.
Run with backend stopped:
    python scripts/fix_data_quality.py
"""

from __future__ import annotations

import duckdb

LOGS_DB = "./data/duckdb/logs.duckdb"
MOCK_DATA_BASE = "./aaop-mock-data/aaop_company"


def fix_medianova(conn: duckdb.DuckDBPyConnection) -> int:
    """Sorun 1: medianova_logs empty — bulk ingest via DuckDB read_json."""
    print("=" * 60)
    print("FIX 1: medianova_logs — DuckDB native JSONL ingest")

    # Clear existing
    conn.execute("DELETE FROM aaop_company.medianova_logs")

    # Use DuckDB's read_json_auto to scan all JSONL.gz files natively
    conn.execute(f"""
        INSERT INTO aaop_company.medianova_logs
        SELECT
            REPLACE(timestamp, '+00:00Z', '+00:00')::TIMESTAMP AS timestamp,
            'aaop_company' AS tenant_id,
            edge_node AS edge_server,
            remote_addr AS client_ip,
            bytes_sent::BIGINT AS bytes_sent,
            status::INTEGER AS status_code,
            proxy_cache_status AS cache_status,
            CASE WHEN proxy_cache_status IN ('HIT','STALE','UPDATING') THEN 1 ELSE 0 END AS cache_hit,
            channel AS content_id,
            content_type,
            country_code,
            isp,
            stream_type AS device_type,
            http_protocol AS protocol,
            NULL AS error_code,
            (request_time * 1000)::INTEGER AS response_time_ms,
            CURRENT_TIMESTAMP AS ingested_at
        FROM read_json_auto('{MOCK_DATA_BASE}/medianova/**/*.jsonl.gz',
            format='newline_delimited', compression='gzip', ignore_errors=true)
    """)

    r = conn.execute("""
        SELECT COUNT(*), MIN(timestamp)::DATE, MAX(timestamp)::DATE, COUNT(DISTINCT timestamp::DATE)
        FROM aaop_company.medianova_logs
    """).fetchone()
    print(f"  Ingested: {r[0]:,} rows")
    print(f"  Date range: {r[1]} → {r[2]}, {r[3]} distinct days")
    return r[0]


def fix_crm_timestamps(conn: duckdb.DuckDBPyConnection) -> int:
    """Sorun 2: crm_subscriber_logs all NULL timestamps — distribute synthetically."""
    print()
    print("=" * 60)
    print("FIX 2: crm_subscriber_logs — fill NULL timestamps + missing fields")

    r = conn.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN timestamp IS NULL THEN 1 ELSE 0 END)
        FROM aaop_company.crm_subscriber_logs
    """).fetchone()
    print(f"  Before: {r[0]:,} rows, {r[1]:,} NULL timestamps")

    if r[1] == 0:
        print("  No NULLs — skipping")
        return 0

    # Rebuild table with synthetic timestamps distributed over 28 days
    conn.execute("""
        CREATE OR REPLACE TABLE aaop_company.crm_subscriber_logs AS
        SELECT
            COALESCE(timestamp,
                CURRENT_DATE - INTERVAL (ROW_NUMBER() OVER () % 28) DAY
                + INTERVAL (floor(random()*24)::INT) HOUR
                + INTERVAL (floor(random()*60)::INT) MINUTE
            ) AS timestamp,
            tenant_id,
            COALESCE(subscriber_id,
                'sub_' || (100000 + ROW_NUMBER() OVER () % 500000)::VARCHAR
            ) AS subscriber_id,
            COALESCE(subscription_tier,
                (ARRAY['basic','standard','premium'])[1 + (ROW_NUMBER() OVER () % 3)::INT]
            ) AS subscription_tier,
            churn_risk,
            COALESCE(lifetime_value, 10.0 + random() * 490.0) AS lifetime_value,
            COALESCE(country_code,
                (ARRAY['TR','DE','UK','US','NL','FR'])[1 + (ROW_NUMBER() OVER () % 6)::INT]
            ) AS country_code,
            COALESCE(device_type,
                (ARRAY['mobile_android','mobile_ios','smart_tv','web','stb'])[1 + (ROW_NUMBER() OVER () % 5)::INT]
            ) AS device_type,
            ingested_at
        FROM aaop_company.crm_subscriber_logs
    """)

    r2 = conn.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN timestamp IS NULL THEN 1 ELSE 0 END),
               MIN(timestamp)::DATE, MAX(timestamp)::DATE, COUNT(DISTINCT timestamp::DATE)
        FROM aaop_company.crm_subscriber_logs
    """).fetchone()
    print(f"  After: {r2[0]:,} rows, {r2[1]} NULL timestamps")
    print(f"  Date range: {r2[2]} → {r2[3]}, {r2[4]} distinct days")
    return r[1]


def copy_fixes_to_sport_stream(conn: duckdb.DuckDBPyConnection) -> None:
    """Copy fixed tables to sport_stream schema."""
    print()
    print("=" * 60)
    print("COPY fixes to sport_stream schema")

    for table in ["medianova_logs", "crm_subscriber_logs"]:
        conn.execute(f"DROP TABLE IF EXISTS sport_stream.{table}")
        conn.execute(f"CREATE TABLE sport_stream.{table} AS SELECT * FROM aaop_company.{table}")
        cnt = conn.execute(f"SELECT COUNT(*) FROM sport_stream.{table}").fetchone()[0]
        print(f"  sport_stream.{table}: {cnt:,} rows")


def main() -> None:
    print("S-DATA-FIX-01 — Mock Data Quality Fixes")
    print()

    conn = duckdb.connect(LOGS_DB)

    n1 = fix_medianova(conn)
    n2 = fix_crm_timestamps(conn)
    copy_fixes_to_sport_stream(conn)

    conn.close()

    print()
    print("=" * 60)
    print("SUMMARY")
    print(f"  Medianova: {n1:,} rows ingested")
    print(f"  CRM: {n2:,} NULL timestamps fixed")
    print("Done.")


if __name__ == "__main__":
    main()
