"""Viewer Experience API router — /viewer prefix."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/viewer", tags=["viewer-experience"])

_schema_ready = False


async def _ensure_schema(db: SQLiteClient) -> None:
    global _schema_ready
    if _schema_ready:
        return
    _schema_ready = True
    await db.execute("""CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, title TEXT NOT NULL,
        category TEXT, content TEXT, sentiment TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'P3', status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT (datetime('now'))
    )""")


class ComplaintCreate(BaseModel):
    title: str
    category: str = ""
    content: str = ""


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "viewer_experience"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    tid = ctx.tenant_id

    # Avg QoE
    avg_row = duck.fetch_one("SELECT AVG(quality_score) as avg_s FROM shared_analytics.qoe_metrics WHERE tenant_id = ?", [tid])
    avg_qoe = round(float(avg_row["avg_s"]), 2) if avg_row and avg_row["avg_s"] else 0.0

    # Below threshold
    below_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.qoe_metrics WHERE tenant_id = ? AND quality_score < 2.5", [tid])
    below = below_row["cnt"] if below_row else 0

    # Active complaints
    comp_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM complaints WHERE tenant_id = ? AND status = 'open'", (tid,))
    active_complaints = comp_row["cnt"] if comp_row else 0

    # Total sessions
    total_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.qoe_metrics WHERE tenant_id = ?", [tid])
    total_sessions = total_row["cnt"] if total_row else 0

    # QoE trend 24h
    trend = [{"hour": f"{h:02d}:00", "avg_score": 0.0} for h in range(24)]
    try:
        trend_rows = duck.fetch_all(
            "SELECT EXTRACT(HOUR FROM event_ts) as hr, AVG(quality_score) as avg_s FROM shared_analytics.qoe_metrics WHERE tenant_id = ? GROUP BY hr ORDER BY hr",
            [tid],
        )
        for r in trend_rows:
            h = int(r["hr"])
            if 0 <= h < 24:
                trend[h]["avg_score"] = round(float(r["avg_s"]), 2)
    except Exception:
        pass

    # Score distribution
    dist_rows = duck.fetch_all("SELECT quality_score FROM shared_analytics.qoe_metrics WHERE tenant_id = ?", [tid])
    dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for r in dist_rows:
        s = float(r["quality_score"]) if r.get("quality_score") else 0
        if s >= 4.0:
            dist["excellent"] += 1
        elif s >= 3.0:
            dist["good"] += 1
        elif s >= 2.0:
            dist["fair"] += 1
        else:
            dist["poor"] += 1

    # Device breakdown
    dev_rows = duck.fetch_all("SELECT device_type, COUNT(*) as cnt FROM shared_analytics.qoe_metrics WHERE tenant_id = ? GROUP BY device_type", [tid])
    device_breakdown = {r["device_type"]: r["cnt"] for r in dev_rows}

    return {
        "avg_qoe_score": avg_qoe,
        "sessions_below_threshold": below,
        "active_complaints": active_complaints,
        "total_sessions_24h": total_sessions,
        "qoe_trend_24h": trend,
        "score_distribution": dist,
        "device_breakdown": device_breakdown,
    }


@router.get("/qoe/metrics")
async def qoe_metrics(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    limit: int = 50,
    offset: int = 0,
    device: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if device:
        where += " AND device_type = ?"
        params.append(device)

    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.qoe_metrics {where}", params)
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.qoe_metrics {where} ORDER BY event_ts DESC LIMIT ? OFFSET ?", [*params, limit, offset])
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/qoe/anomalies")
async def qoe_anomalies(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id
    rows = duck.fetch_all(
        "SELECT * FROM shared_analytics.qoe_metrics WHERE tenant_id = ? AND quality_score < 2.5 ORDER BY quality_score ASC LIMIT 50",
        [tid],
    )
    return {"items": rows, "total": len(rows)}


@router.get("/complaints")
async def list_complaints(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    await _ensure_schema(db)
    where = "WHERE tenant_id = ?"
    params: list[Any] = [ctx.tenant_id]
    if status:
        where += " AND status = ?"
        params.append(status)
    if priority:
        where += " AND priority = ?"
        params.append(priority)
    if category:
        where += " AND category = ?"
        params.append(category)

    count_row = await db.fetch_one(f"SELECT COUNT(*) as cnt FROM complaints {where}", tuple(params))
    total = count_row["cnt"] if count_row else 0

    rows = await db.fetch_all(f"SELECT * FROM complaints {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))
    return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/complaints")
async def create_complaint(
    payload: ComplaintCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    cid = f"CMP-{uuid.uuid4().hex[:10]}"
    await db.execute(
        "INSERT INTO complaints (id, tenant_id, title, category, content) VALUES (?,?,?,?,?)",
        (cid, ctx.tenant_id, payload.title, payload.category, payload.content),
    )
    return {"id": cid, "title": payload.title, "status": "open", "priority": "P3", "sentiment": "pending"}


@router.get("/trends")
async def trends(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    tid = ctx.tenant_id

    dev_rows = duck.fetch_all("SELECT device_type as device, AVG(quality_score) as avg_score FROM shared_analytics.qoe_metrics WHERE tenant_id = ? GROUP BY device_type", [tid])
    qoe_by_device = [{"device": r["device"], "avg_score": round(float(r["avg_score"]), 2)} for r in dev_rows]

    reg_rows = duck.fetch_all("SELECT region, AVG(quality_score) as avg_score FROM shared_analytics.qoe_metrics WHERE tenant_id = ? GROUP BY region", [tid])
    qoe_by_region = [{"region": r["region"], "avg_score": round(float(r["avg_score"]), 2)} for r in reg_rows]

    cat_rows = await db.fetch_all("SELECT category, COUNT(*) as cnt FROM complaints WHERE tenant_id = ? GROUP BY category", (tid,))
    complaint_cats = [{"category": r["category"], "count": r["cnt"]} for r in cat_rows]

    return {
        "qoe_by_device": qoe_by_device,
        "qoe_by_region": qoe_by_region,
        "qoe_by_hour_7d": [],
        "complaint_categories": complaint_cats,
    }
