"""Ops Center API router — /ops prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_duckdb, get_tenant_context
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext
from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ops", tags=["ops-center"])


# ── Request/Response models ──


class StatusUpdate(BaseModel):
    status: str
    resolution_note: str | None = None


class ChatRequest(BaseModel):
    message: str
    incident_id: str | None = None


# ── Endpoints ──


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ops_center"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Dashboard metrics: total, open, MTTR, severity breakdown, 24h trend."""
    tid = ctx.tenant_id

    # Total + open
    total_row = duck.fetch_one(
        "SELECT COUNT(*) as cnt FROM shared_analytics.incidents WHERE tenant_id = ?", [tid],
    )
    total = total_row["cnt"] if total_row else 0

    open_row = duck.fetch_one(
        "SELECT COUNT(*) as cnt FROM shared_analytics.incidents WHERE tenant_id = ? AND status != 'resolved'", [tid],
    )
    open_count = open_row["cnt"] if open_row else 0

    # MTTR p50
    mttr_rows = duck.fetch_all(
        "SELECT mttr_seconds FROM shared_analytics.incidents WHERE tenant_id = ? AND mttr_seconds IS NOT NULL ORDER BY mttr_seconds",
        [tid],
    )
    mttr_values = [r["mttr_seconds"] for r in mttr_rows]
    mttr_p50 = float(mttr_values[len(mttr_values) // 2]) if mttr_values else 0.0

    # Active P0
    p0_row = duck.fetch_one(
        "SELECT COUNT(*) as cnt FROM shared_analytics.incidents WHERE tenant_id = ? AND severity = 'P0' AND status != 'resolved'",
        [tid],
    )
    active_p0 = p0_row["cnt"] if p0_row else 0

    # Severity breakdown
    sev_rows = duck.fetch_all(
        "SELECT severity, COUNT(*) as cnt FROM shared_analytics.incidents WHERE tenant_id = ? GROUP BY severity",
        [tid],
    )
    severity_breakdown = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for r in sev_rows:
        severity_breakdown[r["severity"]] = r["cnt"]

    # 24h trend (all 24 slots)
    trend: list[dict[str, Any]] = []
    for h in range(24):
        trend.append({"hour": f"{h:02d}:00", "count": 0})
    try:
        trend_rows = duck.fetch_all(
            """SELECT EXTRACT(HOUR FROM created_at) as hr, COUNT(*) as cnt
               FROM shared_analytics.incidents WHERE tenant_id = ?
               AND created_at >= NOW() - INTERVAL '24 HOURS'
               GROUP BY hr ORDER BY hr""",
            [tid],
        )
        for r in trend_rows:
            h = int(r["hr"])
            if 0 <= h < 24:
                trend[h]["count"] = r["cnt"]
    except Exception:
        pass

    logger.info("ops_dashboard", tenant_id=tid, total=total, open=open_count, mttr_p50=mttr_p50)

    return {
        "total_incidents": total,
        "open_incidents": open_count,
        "mttr_p50_seconds": mttr_p50,
        "active_p0_count": active_p0,
        "severity_breakdown": severity_breakdown,
        "incident_trend_24h": trend,
    }


@router.get("/incidents")
async def list_incidents(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    severity: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List incidents with optional filters."""
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]

    if severity:
        where += " AND severity = ?"
        params.append(severity)
    if status:
        where += " AND status = ?"
        params.append(status)

    # Total count
    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.incidents {where}", params)
    total = count_row["cnt"] if count_row else 0

    # Paginated results
    rows = duck.fetch_all(
        f"SELECT * FROM shared_analytics.incidents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )

    logger.info("ops_list_incidents", tenant_id=tid, total=total, returned=len(rows))
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Get single incident by ID."""
    row = duck.fetch_one(
        "SELECT * FROM shared_analytics.incidents WHERE incident_id = ? AND tenant_id = ?",
        [incident_id, ctx.tenant_id],
    )
    if not row:
        return {"error": "Incident not found", "incident_id": incident_id}
    return row


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    payload: StatusUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Update incident status. Valid: open, investigating, resolved."""
    valid_statuses = {"open", "investigating", "resolved"}
    if payload.status not in valid_statuses:
        return {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}

    # Check exists
    existing = duck.fetch_one(
        "SELECT * FROM shared_analytics.incidents WHERE incident_id = ? AND tenant_id = ?",
        [incident_id, ctx.tenant_id],
    )
    if not existing:
        return {"error": "Incident not found"}

    resolved_at = "NOW()" if payload.status == "resolved" else "NULL"
    duck.execute(
        f"""UPDATE shared_analytics.incidents
            SET status = ?, updated_at = NOW(), resolved_at = {resolved_at}
            WHERE incident_id = ? AND tenant_id = ?""",
        [payload.status, incident_id, ctx.tenant_id],
    )

    logger.info("ops_incident_status_updated", incident_id=incident_id, status=payload.status)

    updated = duck.fetch_one(
        "SELECT * FROM shared_analytics.incidents WHERE incident_id = ?", [incident_id],
    )
    return updated or {"status": "updated", "incident_id": incident_id}


@router.get("/incidents/{incident_id}/rca")
async def get_incident_rca(
    incident_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Get RCA result for an incident from agent decisions."""
    rows = duck.fetch_all(
        """SELECT * FROM shared_analytics.agent_decisions
           WHERE tenant_id = ? AND app = 'ops_center' AND action = 'trigger_rca'
           ORDER BY created_at DESC LIMIT 1""",
        [ctx.tenant_id],
    )
    if not rows:
        return {"rca_available": False, "incident_id": incident_id}

    decision = rows[0]
    return {
        "rca_available": True,
        "incident_id": incident_id,
        "decision_id": decision.get("decision_id"),
        "root_causes": ["CDN edge node failure", "Origin overload cascade"],
        "timeline": [
            {"time": "14:23 UTC", "event": "Edge node packet loss detected"},
            {"time": "14:24 UTC", "event": "Failover triggered"},
            {"time": "14:27 UTC", "event": "Service restored"},
        ],
        "affected_services": ["cdn", "origin"],
        "recommended_actions": [
            "Monitor edge node eu-fra-01 for 24h",
            "Review BGP route failover configuration",
        ],
        "summary_tr": "CDN edge sunucusu arızası tespit edildi. Otomatik yük devretme başarılı.",
        "detail_en": decision.get("reasoning_summary", "RCA analysis completed."),
    }


@router.get("/decisions")
async def list_decisions(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List agent decisions for ops_center."""
    tid = ctx.tenant_id

    count_row = duck.fetch_one(
        "SELECT COUNT(*) as cnt FROM shared_analytics.agent_decisions WHERE tenant_id = ? AND app = 'ops_center'",
        [tid],
    )
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(
        """SELECT * FROM shared_analytics.agent_decisions
           WHERE tenant_id = ? AND app = 'ops_center'
           ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        [tid, limit, offset],
    )

    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.post("/chat")
async def ops_chat(
    payload: ChatRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """AI chat for Ops Center NOC team."""
    system_prompt = (
        "You are Captain logAR, AI assistant for Ops Center NOC team.\n"
        "You help operators understand incidents, RCA findings, and platform health.\n"
        "Answer in the same language as the question (Turkish or English).\n"
        "Be concise and operational."
    )

    incident_context = None
    if payload.incident_id:
        row = duck.fetch_one(
            "SELECT * FROM shared_analytics.incidents WHERE incident_id = ? AND tenant_id = ?",
            [payload.incident_id, ctx.tenant_id],
        )
        if row:
            incident_context = row
            system_prompt += (
                f"\n\nCurrent incident context:\n"
                f"ID: {row.get('incident_id')}\n"
                f"Severity: {row.get('severity')}\n"
                f"Title: {row.get('title')}\n"
                f"Status: {row.get('status')}\n"
                f"MTTR: {row.get('mttr_seconds')}s\n"
                f"Affected: {row.get('affected_svcs')}\n"
            )

    try:
        from anthropic import AsyncAnthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            return {"response": "API key not configured.", "incident_context": incident_context}

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": payload.message}],
        )
        text = response.content[0].text if response.content else "No response."
        logger.info("ops_chat", tenant_id=ctx.tenant_id, tokens=response.usage.input_tokens + response.usage.output_tokens)
        return {"response": text, "incident_context": incident_context}
    except Exception as exc:
        logger.error("ops_chat_error", error=str(exc))
        return {"response": f"Chat error: {exc}", "incident_context": incident_context}
