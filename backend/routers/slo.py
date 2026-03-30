"""SLO Tracking API router — /slo prefix."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.dependencies import get_sqlite, get_tenant_context
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext
from shared.slo.slo_calculator import SLOCalculator, SLODefinition, SLOMeasurement, SLOStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/slo", tags=["slo"])

_calculator = SLOCalculator()

DEFAULT_SLOS = [
    {"name": "Platform Availability", "metric": "availability", "target": 0.999, "operator": "gte", "description": "Uptime ratio (P0 incident-based)"},
    {"name": "QoE Score", "metric": "qoe_score", "target": 3.5, "operator": "gte", "description": "Average viewer QoE score (0-5)"},
    {"name": "CDN Error Rate", "metric": "cdn_error_rate", "target": 0.05, "operator": "lte", "description": "CDN HTTP error rate"},
    {"name": "API P99 Latency", "metric": "api_p99", "target": 1000.0, "operator": "lte", "description": "API 99th percentile latency (ms)"},
    {"name": "Incident MTTR", "metric": "incident_mttr", "target": 60.0, "operator": "lte", "description": "Mean time to resolve (minutes)"},
]


# ── Models ──────────────────────────────────────────────────────

class SLOCreate(BaseModel):
    name: str
    metric: str
    target: float
    operator: str = "gte"
    description: str = ""
    window_days: int = 30


class SLOUpdate(BaseModel):
    name: str | None = None
    target: float | None = None
    operator: str | None = None
    description: str | None = None
    window_days: int | None = None
    is_active: bool | None = None


# ── Seed ────────────────────────────────────────────────────────

async def seed_slo_tables(sqlite: SQLiteClient) -> None:
    """Create SLO tables and seed defaults — called from lifespan."""
    await sqlite.conn.executescript("""
        CREATE TABLE IF NOT EXISTS slo_definitions (
            id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
            description TEXT, metric TEXT NOT NULL, target REAL NOT NULL,
            operator TEXT NOT NULL, window_days INTEGER DEFAULT 30,
            is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS slo_measurements (
            id TEXT PRIMARY KEY, slo_id TEXT NOT NULL REFERENCES slo_definitions(id),
            tenant_id TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
            measured_value REAL NOT NULL, target REAL NOT NULL, is_met INTEGER NOT NULL,
            error_budget_pct REAL, measured_at TEXT DEFAULT (datetime('now'))
        );
    """)
    await sqlite.conn.commit()

    # Seed defaults per tenant
    tenants = await sqlite.fetch_all("SELECT id FROM tenants WHERE status = 'active'")
    for tenant in tenants:
        tid = tenant["id"]
        for slo in DEFAULT_SLOS:
            existing = await sqlite.fetch_one(
                "SELECT id FROM slo_definitions WHERE tenant_id = ? AND metric = ?",
                (tid, slo["metric"]),
            )
            if not existing:
                await sqlite.execute(
                    "INSERT INTO slo_definitions (id, tenant_id, name, description, metric, target, operator) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex[:12], tid, slo["name"], slo["description"], slo["metric"], slo["target"], slo["operator"]),
                )
    logger.info("slo_tables_seeded")


# ── Helpers ─────────────────────────────────────────────────────

async def _get_definitions(sqlite: SQLiteClient, tenant_id: str) -> list[SLODefinition]:
    rows = await sqlite.fetch_all(
        "SELECT * FROM slo_definitions WHERE tenant_id = ? ORDER BY name", (tenant_id,),
    )
    return [SLODefinition(
        id=r["id"], tenant_id=r["tenant_id"], name=r["name"],
        description=r.get("description", ""), metric=r["metric"],
        target=r["target"], operator=r["operator"],
        window_days=r.get("window_days", 30), is_active=bool(r.get("is_active", 1)),
    ) for r in rows]


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/definitions")
async def list_definitions(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> list[dict]:
    defs = await _get_definitions(sqlite, ctx.tenant_id)
    return [d.model_dump() for d in defs]


@router.post("/definitions", status_code=201)
async def create_definition(
    body: SLOCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> dict:
    slo_id = uuid.uuid4().hex[:12]
    await sqlite.execute(
        "INSERT INTO slo_definitions (id, tenant_id, name, description, metric, target, operator, window_days) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (slo_id, ctx.tenant_id, body.name, body.description, body.metric, body.target, body.operator, body.window_days),
    )
    return {"id": slo_id, "name": body.name, "metric": body.metric, "target": body.target}


@router.patch("/definitions/{slo_id}")
async def update_definition(
    slo_id: str, body: SLOUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [slo_id, ctx.tenant_id]
    await sqlite.execute(f"UPDATE slo_definitions SET {set_clause} WHERE id = ? AND tenant_id = ?", tuple(values))
    return {"id": slo_id, **updates}


@router.delete("/definitions/{slo_id}")
async def delete_definition(
    slo_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> dict:
    await sqlite.execute("DELETE FROM slo_measurements WHERE slo_id = ? AND tenant_id = ?", (slo_id, ctx.tenant_id))
    await sqlite.execute("DELETE FROM slo_definitions WHERE id = ? AND tenant_id = ?", (slo_id, ctx.tenant_id))
    return {"deleted": slo_id}


@router.get("/status")
async def slo_status(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> list[dict]:
    defs = await _get_definitions(sqlite, ctx.tenant_id)
    schema = getattr(ctx, "service_id", "sport_stream") or "sport_stream"
    measurements = await _calculator.calculate_all(defs, ctx.tenant_id, schema)

    statuses = []
    for slo, m in zip(defs, measurements):
        statuses.append(SLOStatus(
            slo_id=slo.id, name=slo.name, metric=slo.metric,
            target=slo.target, operator=slo.operator,
            current_value=m.measured_value, is_met=m.is_met,
            error_budget_remaining_pct=m.error_budget_pct,
            period_days=slo.window_days,
        ).model_dump())
    return statuses


@router.get("/history/{slo_id}")
async def slo_history(
    slo_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
    days: int = Query(default=90),
) -> list[dict]:
    rows = await sqlite.fetch_all(
        "SELECT * FROM slo_measurements WHERE slo_id = ? AND tenant_id = ? ORDER BY measured_at DESC LIMIT ?",
        (slo_id, ctx.tenant_id, days),
    )
    return [dict(r) for r in rows]


@router.post("/calculate")
async def calculate_slos(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
) -> list[dict]:
    defs = await _get_definitions(sqlite, ctx.tenant_id)
    schema = getattr(ctx, "service_id", "sport_stream") or "sport_stream"
    measurements = await _calculator.calculate_all(defs, ctx.tenant_id, schema)

    # Persist measurements
    for m in measurements:
        await sqlite.execute(
            "INSERT INTO slo_measurements (id, slo_id, tenant_id, period_start, period_end, "
            "measured_value, target, is_met, error_budget_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (m.id, m.slo_id, m.tenant_id, m.period_start, m.period_end,
             m.measured_value, m.target, 1 if m.is_met else 0, m.error_budget_pct),
        )

    return [m.model_dump() for m in measurements]


@router.get("/report")
async def slo_report(
    ctx: TenantContext = Depends(get_tenant_context),
    sqlite: SQLiteClient = Depends(get_sqlite),
    period_days: int = Query(default=30),
) -> dict:
    defs = await _get_definitions(sqlite, ctx.tenant_id)
    schema = getattr(ctx, "service_id", "sport_stream") or "sport_stream"
    measurements = await _calculator.calculate_all(defs, ctx.tenant_id, schema)

    met_count = sum(1 for m in measurements if m.is_met)
    return {
        "tenant_id": ctx.tenant_id,
        "period_days": period_days,
        "total_slos": len(measurements),
        "met": met_count,
        "breached": len(measurements) - met_count,
        "slos": [m.model_dump() for m in measurements],
    }
