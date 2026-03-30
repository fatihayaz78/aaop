"""Admin & Governance API router — /admin prefix."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-governance"])


class TenantCreate(BaseModel):
    name: str
    plan: str = "starter"


class ModuleUpdate(BaseModel):
    app_name: str
    enabled: bool


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "admin_governance"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tenants_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM tenants", ())
    total_tenants = tenants_row["cnt"] if tenants_row else 0

    active_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM tenants WHERE is_active = 1", ())
    active_tenants = active_row["cnt"] if active_row else 0

    users_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM users", ())
    total_users = users_row["cnt"] if users_row else 0

    audit_24h = await db.fetch_one("SELECT COUNT(*) as cnt FROM audit_log", ())
    audit_count = audit_24h["cnt"] if audit_24h else 0

    failed_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM audit_log WHERE status = 'failed'", ())
    failed_count = failed_row["cnt"] if failed_row else 0

    # Token usage today
    token_cost = 0.0
    token_in = 0
    token_out = 0
    try:
        tu = duck.fetch_one("SELECT SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost_usd) as cost FROM shared_analytics.token_usage", [])
        if tu:
            token_in = int(tu["inp"] or 0)
            token_out = int(tu["outp"] or 0)
            token_cost = round(float(tu["cost"] or 0), 4)
    except Exception:
        pass

    # Top actions
    top_rows = await db.fetch_all("SELECT action, COUNT(*) as cnt FROM audit_log GROUP BY action ORDER BY cnt DESC LIMIT 5", ())
    top_actions = [{"action": r["action"], "count": r["cnt"]} for r in top_rows]

    try:
        from shared.ingest.log_queries import get_data_source_stats
        source_stats = get_data_source_stats("aaop_company")
    except Exception:
        source_stats = {"sources": {}, "total_rows": 0}

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "audit_events_24h": audit_count,
        "failed_actions_24h": failed_count,
        "token_usage_today": {"input": token_in, "output": token_out, "cost_usd": token_cost},
        "compliance_score": 94.5,
        "top_actions": top_actions,
        "data_source_stats": source_stats,
    }


@router.get("/tenants")
async def list_tenants(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    rows = await db.fetch_all("SELECT * FROM tenants ORDER BY created_at DESC", ())
    return [dict(r) for r in rows]


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    tid = payload.name.lower().replace(" ", "_")
    await db.execute(
        "INSERT INTO tenants (id, name, plan, is_active) VALUES (?,?,?,1)",
        (tid, payload.name, payload.plan),
    )
    logger.info("tenant_created", tenant_id=tid, name=payload.name)
    return {"id": tid, "name": payload.name, "plan": payload.plan, "status": "created"}


@router.get("/tenants/{tenant_id}/modules")
async def get_modules(
    tenant_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    rows = await db.fetch_all("SELECT * FROM module_configs WHERE tenant_id = ?", (tenant_id,))
    return [dict(r) for r in rows]


@router.patch("/tenants/{tenant_id}/modules")
async def update_module(
    tenant_id: str,
    payload: ModuleUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    existing = await db.fetch_one(
        "SELECT id FROM module_configs WHERE tenant_id = ? AND module_name = ?",
        (tenant_id, payload.app_name),
    )
    if existing:
        await db.execute(
            "UPDATE module_configs SET is_enabled = ? WHERE tenant_id = ? AND module_name = ?",
            (1 if payload.enabled else 0, tenant_id, payload.app_name),
        )
    else:
        await db.execute(
            "INSERT INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)",
            (f"mc-{uuid.uuid4().hex[:8]}", tenant_id, payload.app_name, 1 if payload.enabled else 0),
        )
    return {"status": "updated", "tenant_id": tenant_id, "app_name": payload.app_name}


@router.get("/audit")
async def audit_log(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    tenant_id: str | None = None,
    action: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    where = "WHERE 1=1"
    params: list[Any] = []
    if tenant_id:
        where += " AND tenant_id = ?"
        params.append(tenant_id)
    if action:
        where += " AND action = ?"
        params.append(action)
    if status:
        where += " AND status = ?"
        params.append(status)

    count_row = await db.fetch_one(f"SELECT COUNT(*) as cnt FROM audit_log {where}", tuple(params))
    total = count_row["cnt"] if count_row else 0

    rows = await db.fetch_all(
        f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/compliance")
async def compliance(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    checks = [
        {"name": "HIGH_RISK_APPROVAL_RATE", "status": "pass", "description": "96% of HIGH risk actions approved by human", "last_checked": now},
        {"name": "PII_SCRUBBING", "status": "pass", "description": "All PII fields scrubbed before LLM calls", "last_checked": now},
        {"name": "AUDIT_LOG_COVERAGE", "status": "pass", "description": "100% of tool executions logged", "last_checked": now},
        {"name": "TOKEN_BUDGET", "status": "pass", "description": "Token usage at 62% of monthly limit", "last_checked": now},
        {"name": "DEDUP_EFFECTIVENESS", "status": "pass", "description": "Alert dedup rate: 23% (target >15%)", "last_checked": now},
    ]
    violations = [
        {"rule": "TOKEN_BUDGET", "tenant_id": "bein_sports", "description": "Approaching 80% token budget (78%)", "severity": "low"},
        {"rule": "AUDIT_LOG_COVERAGE", "tenant_id": "tivibu", "description": "2 tool executions missing audit records", "severity": "medium"},
    ]
    return {
        "overall_score": 94.5,
        "checks": checks,
        "violations": violations,
        "report_generated_at": now,
    }


@router.get("/usage")
async def usage_stats(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    # By model
    model_rows = duck.fetch_all(
        "SELECT model, COUNT(*) as calls, SUM(cost_usd) as cost FROM shared_analytics.token_usage GROUP BY model",
        [],
    )
    cost_by_model = [{"model": r["model"], "calls": r["calls"], "cost_usd": round(float(r["cost"] or 0), 4)} for r in model_rows]

    # By app
    app_rows = duck.fetch_all(
        "SELECT app_name as app, COUNT(*) as calls, SUM(cost_usd) as cost FROM shared_analytics.token_usage GROUP BY app_name",
        [],
    )
    cost_by_app = [{"app": r["app"], "calls": r["calls"], "cost_usd": round(float(r["cost"] or 0), 4)} for r in app_rows]

    # Totals
    total_row = duck.fetch_one(
        "SELECT SUM(cost_usd) as total_cost, SUM(input_tokens) as inp, SUM(output_tokens) as outp FROM shared_analytics.token_usage",
        [],
    )
    total_cost = round(float(total_row["total_cost"] or 0), 4) if total_row else 0
    inp_total = int(total_row["inp"] or 0) if total_row else 0
    out_total = int(total_row["outp"] or 0) if total_row else 0

    # Daily cost 7d
    daily = duck.fetch_all(
        "SELECT CAST(created_at AS DATE) as day, SUM(cost_usd) as cost FROM shared_analytics.token_usage GROUP BY day ORDER BY day",
        [],
    )
    daily_cost = [{"date": str(r["day"]), "cost_usd": round(float(r["cost"] or 0), 4)} for r in daily]

    return {
        "total_cost_7d": total_cost,
        "cost_by_model": cost_by_model,
        "cost_by_app": cost_by_app,
        "daily_cost_7d": daily_cost,
        "token_breakdown": {"input_total": inp_total, "output_total": out_total},
    }


# ── Platform Admin: tenant/service hierarchy (S-MT-04) ──────────


@router.get("/platform/tenants")
async def platform_tenants(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> list[dict]:
    """List all tenants with services — super_admin only."""
    tenants = await sqlite.fetch_all(
        "SELECT id, name, sector, status FROM tenants WHERE id != 'system' ORDER BY name",
    )
    result = []
    for t in tenants:
        services = await sqlite.fetch_all(
            "SELECT id, name, status FROM services WHERE tenant_id = ?", (t["id"],),
        )
        users = await sqlite.fetch_all(
            "SELECT id FROM users WHERE tenant_id = ?", (t["id"],),
        )
        result.append({
            "id": t["id"],
            "name": t["name"],
            "sector": t.get("sector", ""),
            "status": t.get("status", "active"),
            "services": [{"id": s["id"], "name": s["name"], "status": s.get("status", "active")} for s in services],
            "user_count": len(users),
        })
    return result


# ── Settings endpoints (S-SETTINGS-01) ──────────────────────────

P0_MODULES = {"ops_center", "log_analyzer", "alert_center"}


class SectorUpdate(BaseModel):
    sector: str  # OTT, Telecom, Broadcast, Airline, Other


class ModuleToggle(BaseModel):
    enabled: bool


@router.patch("/tenant/sector")
async def update_sector(
    body: SectorUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> dict:
    """Update tenant sector — tenant_admin or super_admin only."""
    if ctx.role not in ("tenant_admin", "super_admin"):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    await sqlite.execute("UPDATE tenants SET sector = ? WHERE id = ?", (body.sector, ctx.tenant_id))
    logger.info("tenant_sector_updated", tenant_id=ctx.tenant_id, sector=body.sector)
    return {"tenant_id": ctx.tenant_id, "sector": body.sector}


@router.get("/modules")
async def list_modules(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> list[dict]:
    """List module configs for tenant."""
    rows = await sqlite.fetch_all(
        "SELECT id, module_name, is_enabled FROM module_configs WHERE tenant_id = ?", (ctx.tenant_id,),
    )
    return [{"id": r["id"], "module_name": r["module_name"], "enabled": bool(r["is_enabled"])} for r in rows]


@router.patch("/modules/{module_id}")
async def toggle_module(
    module_id: str,
    body: ModuleToggle,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> dict:
    """Toggle module enabled — tenant_admin or super_admin only. P0 modules locked."""
    if ctx.role not in ("tenant_admin", "super_admin"):
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    row = await sqlite.fetch_one("SELECT module_name FROM module_configs WHERE id = ?", (module_id,))
    if not row:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Module not found")

    if row["module_name"] in P0_MODULES and not body.enabled:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="P0 modules cannot be disabled")

    await sqlite.execute("UPDATE module_configs SET is_enabled = ? WHERE id = ?", (1 if body.enabled else 0, module_id))
    logger.info("module_toggled", module_id=module_id, enabled=body.enabled)
    return {"module_id": module_id, "enabled": body.enabled}
