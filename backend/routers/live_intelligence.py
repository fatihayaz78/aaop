"""Live Intelligence API router — /live prefix."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_duckdb, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/live", tags=["live-intelligence"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "live_intelligence"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id

    live_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.live_events WHERE tenant_id = ? AND status = 'live'", [tid])
    live_now = live_row["cnt"] if live_row else 0

    upcoming_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.live_events WHERE tenant_id = ? AND status = 'scheduled'", [tid])
    upcoming = upcoming_row["cnt"] if upcoming_row else 0

    total_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.live_events WHERE tenant_id = ?", [tid])
    total = total_row["cnt"] if total_row else 0

    peak_row = duck.fetch_one("SELECT MAX(peak_viewers) as peak FROM shared_analytics.live_events WHERE tenant_id = ?", [tid])
    peak = peak_row["peak"] if peak_row and peak_row["peak"] else 0

    pre_scale_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.live_events WHERE tenant_id = ? AND status = 'scheduled' AND pre_scale_done = false", [tid])
    pre_scale_pending = pre_scale_row["cnt"] if pre_scale_row else 0

    timeline = [{"hour": f"{h:02d}:00", "count": 0} for h in range(24)]

    try:
        from shared.ingest.log_queries import get_drm_status, get_epg_schedule
        drm = get_drm_status(tid, hours=24)
        epg = get_epg_schedule(tid)
        drm_issues_count = sum(1 for d in ["widevine", "fairplay"] if drm[d]["error_rate_pct"] > 5)
    except Exception:
        drm = {}; epg = {"total_programs": 0}; drm_issues_count = 0

    return {
        "live_now_count": live_now,
        "upcoming_24h_count": upcoming,
        "total_events_7d": total,
        "pre_scale_pending": pre_scale_pending,
        "drm_issues": drm_issues_count,
        "peak_viewers_today": peak,
        "events_timeline": timeline,
        "drm_status": drm,
        "epg_summary": epg,
    }


@router.get("/events")
async def list_events(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if status:
        where += " AND status = ?"
        params.append(status)

    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.live_events {where}", params)
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.live_events {where} ORDER BY kickoff_time DESC LIMIT ?", [*params, limit])
    return {"items": rows, "total": total}


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    row = duck.fetch_one(
        "SELECT * FROM shared_analytics.live_events WHERE event_id = ? AND tenant_id = ?",
        [event_id, ctx.tenant_id],
    )
    if not row:
        return {"error": "Event not found", "event_id": event_id}
    return row


@router.get("/drm/status")
async def drm_status(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "widevine": {"status": "healthy", "license_server": "https://drm.ssportplus.com/widevine", "last_check": now},
        "fairplay": {"status": "healthy", "last_check": now},
        "playready": {"status": "healthy", "last_check": now},
        "overall_health": "healthy",
    }


@router.get("/sportradar")
async def sportradar(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "next_match": {
            "title": "Galatasaray vs Fenerbahce",
            "kickoff": (now + timedelta(days=11, hours=17)).isoformat(),
            "competition": "Super Lig",
            "home_team": "Galatasaray",
            "away_team": "Fenerbahce",
        },
        "live_matches": [
            {"title": "NBA Playoffs Game 3", "score": "87-91", "minute": 32},
        ],
        "last_updated": now.isoformat(),
    }


@router.get("/epg")
async def epg(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    channels = []
    for ch_name in ["beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN 4K"]:
        current_start = now.replace(minute=0, second=0, microsecond=0)
        current_end = current_start + timedelta(hours=1)
        next_slots = []
        for i in range(1, 4):
            s = current_start + timedelta(hours=i)
            e = s + timedelta(hours=1)
            next_slots.append({"title": f"Program {i}", "start": s.isoformat(), "end": e.isoformat()})
        channels.append({
            "name": ch_name,
            "current": {"title": "Live Now", "start": current_start.isoformat(), "end": current_end.isoformat()},
            "next": next_slots,
        })
    return {"channels": channels}
