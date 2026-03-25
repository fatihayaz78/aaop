"""Capacity & Cost API router — /capacity prefix."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/capacity", tags=["capacity-cost"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "capacity_cost"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id

    warn_row = duck.fetch_one("SELECT COUNT(DISTINCT service) as cnt FROM shared_analytics.capacity_metrics WHERE tenant_id = ? AND utilization_pct > 70", [tid])
    warning = warn_row["cnt"] if warn_row else 0

    crit_row = duck.fetch_one("SELECT COUNT(DISTINCT service) as cnt FROM shared_analytics.capacity_metrics WHERE tenant_id = ? AND utilization_pct > 90", [tid])
    critical = crit_row["cnt"] if crit_row else 0

    avg_row = duck.fetch_one("SELECT AVG(utilization_pct) as avg_pct FROM shared_analytics.capacity_metrics WHERE tenant_id = ?", [tid])
    avg_util = round(float(avg_row["avg_pct"]), 1) if avg_row and avg_row["avg_pct"] else 0.0

    peak_row = duck.fetch_one("SELECT service, utilization_pct FROM shared_analytics.capacity_metrics WHERE tenant_id = ? ORDER BY utilization_pct DESC LIMIT 1", [tid])
    peak_svc = peak_row["service"] if peak_row else "—"

    # By service (latest per service)
    svc_rows = duck.fetch_all(
        "SELECT service, current_value as current, capacity_limit as lim, utilization_pct as pct FROM shared_analytics.capacity_metrics WHERE tenant_id = ? ORDER BY timestamp DESC", [tid])
    seen = set()
    by_svc = []
    for r in svc_rows:
        if r["service"] not in seen:
            seen.add(r["service"])
            by_svc.append({"service": r["service"], "current": r["current"], "limit": r["lim"], "pct": r["pct"]})

    # 24h trend
    trend = [{"hour": f"{h:02d}:00", "avg_pct": 0.0} for h in range(24)]
    try:
        trend_rows = duck.fetch_all(
            "SELECT EXTRACT(HOUR FROM CAST(timestamp AS TIMESTAMPTZ)) as hr, AVG(utilization_pct) as avg_pct FROM shared_analytics.capacity_metrics WHERE tenant_id = ? GROUP BY hr ORDER BY hr",
            [tid],
        )
        for r in trend_rows:
            h = int(r["hr"])
            if 0 <= h < 24:
                trend[h]["avg_pct"] = round(float(r["avg_pct"]), 1)
    except Exception:
        pass

    return {
        "services_at_warning": warning,
        "services_at_critical": critical,
        "avg_utilization": avg_util,
        "peak_service": peak_svc,
        "cost_estimate_monthly": round(2400 + random.uniform(-200, 200), 2),
        "utilization_by_service": by_svc,
        "utilization_trend_24h": trend,
    }


@router.get("/forecast")
async def forecast(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    forecasts = []
    for svc in ["cdn_bandwidth", "concurrent_streams", "origin_cpu"]:
        for d in range(7):
            pct = round(random.uniform(40, 95), 1)
            conf = round(random.uniform(0.7, 0.95), 2)
            rec = "scale_up" if pct > 80 else "monitor" if pct > 60 else "ok"
            forecasts.append({
                "date": (now + timedelta(days=d)).strftime("%Y-%m-%d"),
                "service": svc, "predicted_pct": pct, "confidence": conf,
                "recommendation": rec,
            })
    return {"forecast": forecasts}


@router.get("/usage")
async def usage(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    service: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if service:
        where += " AND service = ?"
        params.append(service)

    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.capacity_metrics {where}", params)
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.capacity_metrics {where} ORDER BY timestamp DESC LIMIT ?", [*params, limit])
    return {"items": rows, "total": total, "limit": limit}


@router.get("/jobs")
async def automation_jobs(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    try:
        rows = await db.fetch_all("SELECT * FROM automation_jobs WHERE tenant_id = ? ORDER BY created_at DESC", (ctx.tenant_id,))
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/cost")
async def cost_analysis(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    base = 2400
    breakdown = [
        {"service": "CDN", "cost_usd": 1200, "pct_of_total": 50.0},
        {"service": "Encoding", "cost_usd": 600, "pct_of_total": 25.0},
        {"service": "Storage", "cost_usd": 300, "pct_of_total": 12.5},
        {"service": "API", "cost_usd": 200, "pct_of_total": 8.3},
        {"service": "Other", "cost_usd": 100, "pct_of_total": 4.2},
    ]
    return {
        "current_month_usd": base,
        "projected_month_usd": round(base * 1.05, 2),
        "breakdown": breakdown,
        "vs_last_month_pct": round(random.uniform(-5, 8), 1),
        "optimization_tips": [
            "Enable Akamai SureRoute for 12% bandwidth savings",
            "Consolidate origin shield to reduce multi-CDN costs",
            "Switch VOD encoding to HEVC for 30% storage reduction",
        ],
    }
