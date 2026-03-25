"""Seed mock data for Admin & Governance."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient

logger = structlog.get_logger(__name__)

_ACTIONS = ["login", "logout", "create_incident", "update_status", "trigger_rca",
            "export_data", "update_config", "create_alert_rule", "delete_rule", "view_dashboard"]
_APPS = ["ops_center", "alert_center", "viewer_experience", "log_analyzer", "live_intelligence"]
_MODELS = [
    ("claude-haiku-4-5-20251001", 100, 500, 0.0001, 0.001),
    ("claude-sonnet-4-20250514", 200, 1000, 0.001, 0.01),
    ("claude-opus-4-20250514", 500, 2000, 0.01, 0.05),
]
_ALL_APPS = ["ops_center", "log_analyzer", "alert_center", "viewer_experience",
             "live_intelligence", "growth_retention", "capacity_cost",
             "ai_lab", "knowledge_base", "devops_assistant", "admin_governance"]


async def seed_admin_governance_mock_data(
    sqlite: SQLiteClient,
    duck: DuckDBClient,
    tenant_id: str = "s_sport_plus",
) -> None:
    """Seed tenants, module_configs, audit_log, token_usage. Idempotent."""
    # Check if already seeded
    try:
        row = await sqlite.fetch_one("SELECT COUNT(*) as cnt FROM audit_log", ())
        if row and row.get("cnt", 0) >= 10:
            logger.info("admin_seed_skipped", existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # ── Tenants ──
    tenants = [
        ("s_sport_plus", "S Sport Plus", "enterprise"),
        ("bein_sports", "beIN Sports", "pro"),
        ("tivibu", "Tivibu", "starter"),
    ]
    for tid, name, plan in tenants:
        existing = await sqlite.fetch_one("SELECT id FROM tenants WHERE id = ?", (tid,))
        if not existing:
            await sqlite.execute(
                "INSERT OR IGNORE INTO tenants (id, name, plan, is_active) VALUES (?,?,?,1)",
                (tid, name, plan),
            )

    # ── Module configs ──
    existing_mc = await sqlite.fetch_one("SELECT COUNT(*) as cnt FROM module_configs WHERE tenant_id = 's_sport_plus'", ())
    if not existing_mc or existing_mc.get("cnt", 0) < 5:
        # s_sport_plus: all 11 enabled
        for app in _ALL_APPS:
            await sqlite.execute(
                "INSERT OR IGNORE INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)",
                (f"mc-{uuid4().hex[:8]}", "s_sport_plus", app, 1),
            )
        # bein_sports: 3 enabled
        for app in ["ops_center", "log_analyzer", "alert_center"]:
            await sqlite.execute(
                "INSERT OR IGNORE INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)",
                (f"mc-{uuid4().hex[:8]}", "bein_sports", app, 1),
            )
        # tivibu: 1 enabled
        await sqlite.execute(
            "INSERT OR IGNORE INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)",
            (f"mc-{uuid4().hex[:8]}", "tivibu", "log_analyzer", 1),
        )

    # ── Audit log — add status column if missing (built-in table lacks it) ──
    for col in ["status", "resource_id"]:
        try:
            await sqlite.execute(f"ALTER TABLE audit_log ADD COLUMN {col} TEXT DEFAULT 'success'")
        except Exception:
            pass

    tenant_ids = ["s_sport_plus", "bein_sports", "tivibu"]
    for i in range(50):
        tid_choice = random.choice(tenant_ids)
        action = random.choice(_ACTIONS)
        status = "success" if random.random() < 0.9 else "failed"
        ip_hash = hashlib.sha256(f"ip-{random.randint(1,50)}".encode()).hexdigest()[:16]
        await sqlite.execute(
            "INSERT OR IGNORE INTO audit_log (id, tenant_id, user_id, action, resource, status, ip_hash, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"AUD-{uuid4().hex[:10]}", tid_choice, f"user-{random.randint(1,10):03d}",
             action, action.split("_")[0], status, ip_hash,
             (now - timedelta(hours=random.randint(0, 168))).isoformat()),
        )

    # ── DuckDB token_usage ──
    duck.execute("""CREATE TABLE IF NOT EXISTS shared_analytics.token_usage (
        id VARCHAR, tenant_id VARCHAR, app_name VARCHAR, model VARCHAR,
        input_tokens INTEGER, output_tokens INTEGER, cost_usd DOUBLE,
        created_at VARCHAR
    )""")

    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.token_usage WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 50:
            logger.info("admin_seed_tokens_skipped")
            return
    except Exception:
        pass

    for _ in range(200):
        model, min_tok, max_tok, min_cost, max_cost = random.choice(_MODELS)
        inp = random.randint(min_tok, max_tok)
        out = random.randint(min_tok // 2, max_tok // 2)
        cost = round(random.uniform(min_cost, max_cost), 4)
        try:
            duck.execute(
                """INSERT INTO shared_analytics.token_usage
                   (id, tenant_id, app_name, model, input_tokens, output_tokens, cost_usd, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [f"TU-{uuid4().hex[:8]}", tenant_id, random.choice(_APPS), model,
                 inp, out, cost, (now - timedelta(hours=random.randint(0, 168))).isoformat()],
            )
        except Exception:
            pass

    logger.info("admin_seed_complete", tenant_id=tenant_id, audit=50, tokens=200)
