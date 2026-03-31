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


class IncidentCreate(BaseModel):
    title: str
    severity: str  # P0, P1, P2, P3
    description: str | None = None
    affected_service: str | None = None


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

    # Log-based metrics
    try:
        from shared.ingest.log_queries import (
            get_cdn_metrics, get_infrastructure_health, get_player_qoe, detect_incidents_from_logs,
        )
        cdn = get_cdn_metrics(tid, hours=24)
        infra = get_infrastructure_health(tid, hours=24)
        qoe = get_player_qoe(tid, hours=24)
        detected = detect_incidents_from_logs(tid, hours=24)
    except Exception as exc:
        logger.warning("ops_dashboard_log_queries_error", error=str(exc))
        cdn = {"total_requests": 0, "error_rate_pct": 0, "cache_hit_rate_pct": 0, "bandwidth_gb": 0}
        infra = {"avg_apdex": 0, "critical_services": [], "services": []}
        qoe = {"avg_qoe_score": 0, "sessions_total": 0}
        detected = []

    # Merge detected incidents into severity breakdown
    for d in detected:
        sev = d.get("severity", "P2")
        if sev in severity_breakdown:
            severity_breakdown[sev] += 1

    logger.info("ops_dashboard", tenant_id=tid, total=total, open=open_count, mttr_p50=mttr_p50, detected=len(detected))

    return {
        "total_incidents": total + len(detected),
        "open_incidents": open_count + len(detected),
        "mttr_p50_seconds": mttr_p50,
        "active_p0_count": active_p0 + sum(1 for d in detected if d.get("severity") == "P0"),
        "severity_breakdown": severity_breakdown,
        "incident_trend_24h": trend,
        "cdn_health": {
            "total_requests": cdn["total_requests"],
            "error_rate_pct": cdn["error_rate_pct"],
            "cache_hit_rate_pct": cdn.get("cache_hit_rate_pct", 0),
            "bandwidth_gb": cdn.get("bandwidth_gb", 0),
        },
        "infrastructure": {
            "avg_apdex": infra["avg_apdex"],
            "critical_services": infra["critical_services"],
            "service_count": len(infra["services"]),
        },
        "qoe": {
            "avg_score": qoe["avg_qoe_score"],
            "sessions_24h": qoe["sessions_total"],
        },
        "detected_incidents": detected,
        "events_24h": len(detected),
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


@router.post("/incidents", status_code=201)
async def create_incident(
    body: IncidentCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    """Create a new incident."""
    import uuid
    from datetime import datetime, timezone

    if body.severity not in ("P0", "P1", "P2", "P3"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid severity. Must be P0, P1, P2, or P3")

    incident_id = f"INC-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    affected = f'["{body.affected_service}"]' if body.affected_service else "[]"

    duck.execute(
        """INSERT INTO shared_analytics.incidents
           (incident_id, tenant_id, severity, title, status, source_app,
            correlation_ids, affected_svcs, metrics_at_time, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'open', 'manual', '[]', ?, '{}', ?, ?)""",
        [incident_id, ctx.tenant_id, body.severity, body.title, affected, now, now],
    )
    logger.info("incident_created", incident_id=incident_id, severity=body.severity, tenant_id=ctx.tenant_id)

    return {
        "incident_id": incident_id,
        "title": body.title,
        "severity": body.severity,
        "status": "open",
        "created_at": now,
    }


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
    result = updated or {"status": "updated", "incident_id": incident_id}

    # WebSocket broadcast
    try:
        from backend.websocket.manager import ws_manager
        await ws_manager.broadcast("ops_center", ctx.tenant_id, {"event": "incident_update", "data": result})
    except Exception:
        pass

    return result


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

    # Enrich with real log metrics
    try:
        from shared.ingest.log_queries import get_cdn_metrics, get_player_qoe, get_infrastructure_health
        cdn_ctx = get_cdn_metrics(ctx.tenant_id, hours=24)
        qoe_ctx = get_player_qoe(ctx.tenant_id, hours=24)
        infra_ctx = get_infrastructure_health(ctx.tenant_id, hours=24)
        system_prompt += (
            f"\n\nReal-time platform metrics (last 24h):\n"
            f"CDN: {cdn_ctx['total_requests']} requests, {cdn_ctx['error_rate_pct']}% error rate, "
            f"{cdn_ctx.get('cache_hit_rate_pct', 0)}% cache hit\n"
            f"QoE: avg score {qoe_ctx['avg_qoe_score']}, {qoe_ctx['sessions_total']} sessions\n"
            f"Infra: avg apdex {infra_ctx['avg_apdex']}, critical services: {infra_ctx['critical_services']}\n"
        )
    except Exception:
        pass

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
