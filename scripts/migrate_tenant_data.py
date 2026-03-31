"""S-DATA-RESEED-01 — Migrate tenant_id in analytics.duckdb + seed demo data.

Run with backend STOPPED (DuckDB single-writer lock):
    pkill -f uvicorn; sleep 2; python scripts/migrate_tenant_data.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import duckdb

ANALYTICS_DB = "./data/duckdb/analytics.duckdb"

random.seed(42)
NOW = datetime.now(timezone.utc)


def migrate_tenant_ids(conn: duckdb.DuckDBPyConnection) -> None:
    """Step 1: Update old tenant_id values to new multi-tenant schema."""
    print("=" * 60)
    print("STEP 1: Migrate tenant_id in analytics.duckdb")

    mapping = {
        "s_sport_plus": "ott_co",
        "bein_sports": "tel_co",
        "aaop_company": "ott_co",
        "system": "ott_co",
    }

    tables = ["shared_analytics.incidents", "shared_analytics.agent_decisions",
              "shared_analytics.alerts_sent", "shared_analytics.qoe_metrics",
              "shared_analytics.cdn_analysis", "shared_analytics.live_events",
              "shared_analytics.capacity_metrics", "shared_analytics.experiments",
              "shared_analytics.model_registry", "shared_analytics.retention_scores",
              "shared_analytics.token_usage"]

    for table in tables:
        try:
            for old_id, new_id in mapping.items():
                result = conn.execute(
                    f"UPDATE {table} SET tenant_id = '{new_id}' WHERE tenant_id = '{old_id}'"
                )
                affected = result.fetchone()
            # Verify
            rows = conn.execute(f"SELECT tenant_id, COUNT(*) FROM {table} GROUP BY tenant_id").fetchall()
            print(f"  {table}: {rows}")
        except Exception as e:
            print(f"  {table}: SKIP — {e}")


def seed_incidents(conn: duckdb.DuckDBPyConnection) -> int:
    """Step 2a: Seed realistic incidents for ott_co."""
    print()
    print("=" * 60)
    print("STEP 2a: Seed incidents for ott_co")

    # Check existing count
    existing = conn.execute(
        "SELECT COUNT(*) FROM shared_analytics.incidents WHERE tenant_id = 'ott_co'"
    ).fetchone()[0]
    print(f"  Existing: {existing}")

    if existing >= 10:
        print("  Already enough — skipping")
        return 0

    severities = ["P0", "P1", "P1", "P2", "P2", "P2", "P3", "P3", "P3", "P3"]
    statuses = ["resolved", "resolved", "resolved", "open", "investigating",
                "resolved", "open", "resolved", "resolved", "resolved"]
    titles = [
        "CDN Error Rate Spike - Akamai EU",
        "DRM License Server Timeout",
        "Player Buffer Ratio Critical",
        "API Gateway 5xx Surge",
        "Live Stream Quality Drop - Derby Match",
        "Database Connection Pool Exhaustion",
        "CDN Cache Miss Rate Above 40%",
        "Mobile App Crash Rate Elevated",
        "Payment Gateway Timeout",
        "EPG Data Feed Stale",
    ]
    sources = ["log_analyzer", "ops_center", "viewer_experience", "alert_center",
               "live_intelligence", "devops_assistant", "log_analyzer",
               "viewer_experience", "capacity_cost", "live_intelligence"]

    inserted = 0
    for i in range(10):
        incident_id = f"INC-{uuid.uuid4().hex[:12]}"
        created = NOW - timedelta(days=random.randint(0, 6), hours=random.randint(0, 23))
        resolved = created + timedelta(minutes=random.randint(15, 240)) if statuses[i] == "resolved" else None
        mttr = int((resolved - created).total_seconds()) if resolved else None

        try:
            conn.execute("""
                INSERT INTO shared_analytics.incidents
                (incident_id, tenant_id, severity, title, status, source_app,
                 correlation_ids, affected_svcs, metrics_at_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                incident_id, "ott_co", severities[i], titles[i], statuses[i], sources[i],
                "[]", str(["cdn", "player"][: random.randint(1, 2)]),
                json.dumps({"error_rate": round(random.uniform(0.02, 0.15), 4)}),
                created.isoformat(), (resolved or created).isoformat(),
            ])
            inserted += 1
        except Exception as e:
            print(f"  Insert error: {e}")

    # Update mttr_seconds for resolved incidents
    conn.execute("""
        UPDATE shared_analytics.incidents
        SET mttr_seconds = EXTRACT(EPOCH FROM (updated_at::TIMESTAMP - created_at::TIMESTAMP))
        WHERE status = 'resolved' AND tenant_id = 'ott_co' AND mttr_seconds IS NULL
    """)

    print(f"  Inserted: {inserted} incidents")
    return inserted


def seed_decisions(conn: duckdb.DuckDBPyConnection) -> int:
    """Step 2b: Seed agent decisions for ott_co."""
    print()
    print("=" * 60)
    print("STEP 2b: Seed agent_decisions for ott_co")

    existing = conn.execute(
        "SELECT COUNT(*) FROM shared_analytics.agent_decisions WHERE tenant_id = 'ott_co'"
    ).fetchone()[0]
    print(f"  Existing: {existing}")

    if existing >= 10:
        print("  Already enough — skipping")
        return 0

    apps = ["ops_center", "log_analyzer", "alert_center", "viewer_experience",
            "live_intelligence", "growth_retention", "capacity_cost",
            "ops_center", "alert_center", "log_analyzer"]
    actions = ["analyze_incident", "analyze_cdn_logs", "route_alert", "qoe_analysis",
               "monitor_event", "churn_analysis", "capacity_forecast",
               "create_incident", "dedup_drop", "anomaly_detection"]
    models = ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001",
              "claude-haiku-4-5-20251001", "claude-sonnet-4-20250514",
              "claude-sonnet-4-20250514", "claude-sonnet-4-20250514",
              "claude-sonnet-4-20250514", "claude-opus-4-20250514",
              "claude-haiku-4-5-20251001", "claude-sonnet-4-20250514"]
    risks = ["LOW", "LOW", "LOW", "MEDIUM", "LOW", "MEDIUM", "LOW", "HIGH", "LOW", "LOW"]

    inserted = 0
    for i in range(10):
        decision_id = uuid.uuid4().hex[:16]
        created = NOW - timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))

        try:
            conn.execute("""
                INSERT INTO shared_analytics.agent_decisions
                (decision_id, tenant_id, app, action, risk_level, approval_required,
                 llm_model_used, reasoning_summary, tools_executed,
                 confidence_score, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                decision_id, "ott_co", apps[i], actions[i], risks[i],
                risks[i] == "HIGH", models[i],
                f"Agent analyzed {actions[i]} scenario",
                json.dumps([actions[i]]),
                round(random.uniform(0.7, 0.99), 2),
                random.randint(50, 2000),
                created.isoformat(),
            ])
            inserted += 1
        except Exception as e:
            print(f"  Insert error: {e}")

    print(f"  Inserted: {inserted} decisions")
    return inserted


def verify(conn: duckdb.DuckDBPyConnection) -> None:
    """Step 4: Verify results."""
    print()
    print("=" * 60)
    print("VERIFICATION")

    for table in ["shared_analytics.incidents", "shared_analytics.agent_decisions"]:
        rows = conn.execute(f"SELECT tenant_id, COUNT(*) FROM {table} GROUP BY tenant_id").fetchall()
        print(f"  {table}: {rows}")

    # Show ott_co sample
    sample = conn.execute("""
        SELECT incident_id, severity, title, status, created_at
        FROM shared_analytics.incidents
        WHERE tenant_id = 'ott_co'
        ORDER BY created_at DESC
        LIMIT 3
    """).fetchall()
    print(f"\n  Recent ott_co incidents:")
    for r in sample:
        print(f"    {r[0]} [{r[1]}] {r[2]} — {r[3]}")


def main() -> None:
    print("S-DATA-RESEED-01 — Tenant Migration + Demo Data Seed")
    print()

    conn = duckdb.connect(ANALYTICS_DB)

    migrate_tenant_ids(conn)
    seed_incidents(conn)
    seed_decisions(conn)
    verify(conn)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
