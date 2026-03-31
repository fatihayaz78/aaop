"""Alert Center API router — /alerts prefix."""

from __future__ import annotations

import json
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
router = APIRouter(prefix="/alerts", tags=["alert-center"])

# ── Schema init flag ──
_schema_ready = False


async def _ensure_schema(db: SQLiteClient) -> None:
    global _schema_ready
    if _schema_ready:
        return
    _schema_ready = True

    await db.execute("""CREATE TABLE IF NOT EXISTS alert_rules (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
        event_types TEXT NOT NULL, severity_min TEXT NOT NULL, channels TEXT NOT NULL,
        is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS alert_channels (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, channel_type TEXT NOT NULL,
        name TEXT NOT NULL, config_json TEXT NOT NULL, is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS suppression_rules (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
        start_time TEXT NOT NULL, end_time TEXT NOT NULL, is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    # Seed defaults for s_sport_plus
    existing = await db.fetch_one("SELECT id FROM alert_rules WHERE tenant_id = 's_sport_plus' LIMIT 1", ())
    if not existing:
        for name, events, sev, channels in [
            ("CDN Anomaly → Slack", '["cdn_anomaly_detected"]', "P1", '["slack"]'),
            ("QoE Drop → Slack", '["qoe_degradation"]', "P2", '["slack"]'),
            ("Incident → Slack+PD", '["incident_created"]', "P0", '["slack","pagerduty"]'),
            ("Churn Risk → Email", '["churn_risk_detected"]', "P3", '["email"]'),
            ("Scale Rec → Slack", '["scale_recommendation"]', "P2", '["slack"]'),
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO alert_rules (id, tenant_id, name, event_types, severity_min, channels) VALUES (?,?,?,?,?,?)",
                (f"rule-{uuid.uuid4().hex[:8]}", "s_sport_plus", name, events, sev, channels),
            )
        for ch_type, ch_name, cfg in [
            ("slack", "NOC Slack", '{"webhook_url":"https://hooks.slack.com/..."}'),
            ("pagerduty", "On-Call PD", '{"integration_key":"pd-key-***"}'),
            ("email", "NOC Email", '{"to":["noc@ssportplus.com"]}'),
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO alert_channels (id, tenant_id, channel_type, name, config_json) VALUES (?,?,?,?,?)",
                (f"ch-{uuid.uuid4().hex[:8]}", "s_sport_plus", ch_type, ch_name, cfg),
            )
        for sup_name, start, end in [
            ("Weekly Maintenance", "2026-03-26T02:00:00", "2026-03-26T04:00:00"),
            ("Deploy Window", "2026-03-27T01:00:00", "2026-03-27T02:00:00"),
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO suppression_rules (id, tenant_id, name, start_time, end_time) VALUES (?,?,?,?,?)",
                (f"sup-{uuid.uuid4().hex[:8]}", "s_sport_plus", sup_name, start, end),
            )
    logger.info("alert_center_schema_ready")


# ── Models ──

class RulePayload(BaseModel):
    name: str
    event_types: list[str]
    severity_min: str = "P3"
    channels: list[str]
    is_active: int = 1


class SuppressionPayload(BaseModel):
    name: str
    start_time: str
    end_time: str
    is_active: int = 1


# ── Endpoints ──

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "alert_center"}


@router.get("/dashboard")
async def dashboard(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    tid = ctx.tenant_id

    total_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ?", [tid])
    total = total_row["cnt"] if total_row else 0

    active_row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? AND status = 'sent'", [tid])
    active = active_row["cnt"] if active_row else 0

    sev_rows = duck.fetch_all("SELECT severity, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? GROUP BY severity", [tid])
    severity_breakdown = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for r in sev_rows:
        severity_breakdown[r["severity"]] = r["cnt"]

    ch_rows = duck.fetch_all("SELECT channel, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? GROUP BY channel", [tid])
    channel_breakdown = {r["channel"]: r["cnt"] for r in ch_rows} if ch_rows else {}

    trend: list[dict] = [{"hour": f"{h:02d}:00", "count": 0} for h in range(24)]
    try:
        trend_rows = duck.fetch_all(
            "SELECT EXTRACT(HOUR FROM sent_at) as hr, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? AND sent_at >= NOW() - INTERVAL '24 HOURS' GROUP BY hr",
            [tid],
        )
        for r in trend_rows:
            h = int(r["hr"])
            if 0 <= h < 24:
                trend[h]["count"] = r["cnt"]
    except Exception:
        pass

    # Log-based status badges
    try:
        from shared.ingest.log_queries import get_cdn_metrics, get_drm_status, get_api_health
        cdn = get_cdn_metrics(tid, hours=24)
        drm = get_drm_status(tid, hours=24)
        api = get_api_health(tid, hours=24)
        cdn_status = "warning" if cdn["error_rate_pct"] > 5 else "ok"
        drm_status = "warning" if max(drm["widevine"]["error_rate_pct"], drm["fairplay"]["error_rate_pct"]) > 10 else "ok"
        api_status = "warning" if api["error_rate_pct"] > 5 else "ok"
    except Exception:
        cdn_status = drm_status = api_status = "unknown"

    return {
        "total_alerts_24h": total,
        "active_alerts": active,
        "dedup_hit_rate": 0.0,
        "storm_events_7d": 0,
        "severity_breakdown": severity_breakdown,
        "channel_breakdown": channel_breakdown,
        "alert_trend_24h": trend,
        "cdn_status": cdn_status,
        "drm_status": drm_status,
        "api_status": api_status,
    }


@router.get("/list")
async def list_alerts(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
    severity: str | None = None,
    channel: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    tid = ctx.tenant_id
    where = "WHERE tenant_id = ?"
    params: list[Any] = [tid]
    if severity:
        where += " AND severity = ?"
        params.append(severity)
    if channel:
        where += " AND channel = ?"
        params.append(channel)

    count_row = duck.fetch_one(f"SELECT COUNT(*) as cnt FROM shared_analytics.alerts_sent {where}", params)
    total = count_row["cnt"] if count_row else 0

    rows = duck.fetch_all(f"SELECT * FROM shared_analytics.alerts_sent {where} ORDER BY sent_at DESC LIMIT ? OFFSET ?", [*params, limit, offset])
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/rules")
async def list_rules(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    await _ensure_schema(db)
    rows = await db.fetch_all("SELECT * FROM alert_rules WHERE tenant_id = ?", (ctx.tenant_id,))
    return [dict(r) for r in rows]


@router.post("/rules")
async def create_rule(
    payload: RulePayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    rule_id = f"rule-{uuid.uuid4().hex[:8]}"
    await db.execute(
        "INSERT INTO alert_rules (id, tenant_id, name, event_types, severity_min, channels, is_active) VALUES (?,?,?,?,?,?,?)",
        (rule_id, ctx.tenant_id, payload.name, json.dumps(payload.event_types), payload.severity_min, json.dumps(payload.channels), payload.is_active),
    )
    return {"id": rule_id, "status": "created"}


@router.patch("/rules/{rule_id}")
async def patch_rule(
    rule_id: str,
    payload: dict[str, Any],
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, str]:
    await _ensure_schema(db)
    sets = []
    params: list[Any] = []
    for k, v in payload.items():
        if k in ("name", "event_types", "severity_min", "channels", "is_active"):
            sets.append(f"{k} = ?")
            params.append(json.dumps(v) if isinstance(v, list) else v)
    if sets:
        params.extend([rule_id, ctx.tenant_id])
        await db.execute(f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ? AND tenant_id = ?", tuple(params))
    return {"status": "updated", "id": rule_id}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    await db.execute("DELETE FROM alert_rules WHERE id = ? AND tenant_id = ?", (rule_id, ctx.tenant_id))
    return {"deleted": True, "id": rule_id}


@router.get("/channels")
async def list_channels(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    await _ensure_schema(db)
    rows = await db.fetch_all("SELECT * FROM alert_channels WHERE tenant_id = ?", (ctx.tenant_id,))
    return [dict(r) for r in rows]


@router.get("/suppression")
async def list_suppression(
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> list[dict[str, Any]]:
    await _ensure_schema(db)
    rows = await db.fetch_all("SELECT * FROM suppression_rules WHERE tenant_id = ?", (ctx.tenant_id,))
    return [dict(r) for r in rows]


@router.post("/suppression")
async def create_suppression(
    payload: SuppressionPayload,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    await _ensure_schema(db)
    sup_id = f"sup-{uuid.uuid4().hex[:8]}"
    await db.execute(
        "INSERT INTO suppression_rules (id, tenant_id, name, start_time, end_time, is_active) VALUES (?,?,?,?,?,?)",
        (sup_id, ctx.tenant_id, payload.name, payload.start_time, payload.end_time, payload.is_active),
    )
    return {"id": sup_id, "status": "created"}


@router.get("/analytics")
async def analytics(
    ctx: TenantContext = Depends(get_tenant_context),
    duck: DuckDBClient = Depends(get_duckdb),
) -> dict[str, Any]:
    tid = ctx.tenant_id

    # Top event types
    event_rows = duck.fetch_all(
        "SELECT source_app, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? GROUP BY source_app ORDER BY cnt DESC LIMIT 5",
        [tid],
    )
    top_events = [{"event_type": r["source_app"], "count": r["cnt"]} for r in event_rows]

    # Channel performance
    ch_rows = duck.fetch_all(
        "SELECT channel, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? GROUP BY channel",
        [tid],
    )
    channel_perf = {r["channel"]: r["cnt"] for r in ch_rows} if ch_rows else {}

    # Daily volume 7d
    daily = []
    try:
        daily_rows = duck.fetch_all(
            "SELECT CAST(sent_at AS DATE) as day, COUNT(*) as cnt FROM shared_analytics.alerts_sent WHERE tenant_id = ? AND sent_at >= NOW() - INTERVAL '7 DAYS' GROUP BY day ORDER BY day",
            [tid],
        )
        daily = [{"date": str(r["day"]), "count": r["cnt"]} for r in daily_rows]
    except Exception:
        pass

    return {
        "mtta_p50_seconds": 0.0,
        "top_event_types": top_events[:5],
        "channel_performance": channel_perf,
        "daily_volume_7d": daily,
    }


@router.post("/evaluate")
async def evaluate_alerts(
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Run log-based anomaly detection and evaluate alerts."""
    try:
        from shared.ingest.log_queries import detect_incidents_from_logs
        incidents = detect_incidents_from_logs(ctx.tenant_id, hours=1)
        result = {
            "evaluated": len(incidents),
            "routed": len(incidents),
            "suppressed": 0,
            "incidents": incidents,
        }
        # WebSocket broadcast for each detected incident
        try:
            from backend.websocket.manager import ws_manager
            for inc in incidents:
                await ws_manager.broadcast("alert_center", ctx.tenant_id, {"event": "alert_new", "data": inc})
        except Exception:
            pass
        return result
    except Exception as exc:
        logger.warning("alert_evaluate_error", error=str(exc))
        return {"evaluated": 0, "routed": 0, "suppressed": 0, "incidents": []}


# ── Channel test + config (S-API-FIX-01) ────────────────────────

VALID_CHANNELS = {"slack", "pagerduty", "email"}


class ChannelConfig(BaseModel):
    webhook_url: str | None = None
    api_key: str | None = None
    enabled: bool = True


@router.post("/test/{channel_type}")
async def test_channel(
    channel_type: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Simulate a test notification for a channel."""
    if channel_type not in VALID_CHANNELS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid channel. Must be one of: {', '.join(VALID_CHANNELS)}")

    logger.info("channel_test_sent", channel=channel_type, tenant_id=ctx.tenant_id)
    return {"channel": channel_type, "status": "test_sent", "message": f"Test notification simulated for {channel_type}"}


@router.patch("/channels/{channel_type}")
async def update_channel(
    channel_type: str,
    body: ChannelConfig,
    ctx: TenantContext = Depends(get_tenant_context),
    db: SQLiteClient = Depends(get_sqlite),
) -> dict[str, Any]:
    """Update or create channel configuration."""
    if channel_type not in VALID_CHANNELS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid channel type")

    await _ensure_schema(db)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    existing = await db.fetch_one(
        "SELECT id FROM alert_channels WHERE tenant_id = ? AND channel_type = ?",
        (ctx.tenant_id, channel_type),
    )

    config_data = json.dumps({"webhook_url": body.webhook_url, "api_key": body.api_key})

    if existing:
        await db.execute(
            "UPDATE alert_channels SET config_json = ?, is_active = ?, created_at = ? WHERE id = ?",
            (config_data, 1 if body.enabled else 0, now, existing["id"]),
        )
    else:
        import uuid
        ch_id = f"ch-{uuid.uuid4().hex[:8]}"
        await db.execute(
            "INSERT INTO alert_channels (id, tenant_id, channel_type, name, config_json, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (ch_id, ctx.tenant_id, channel_type, channel_type.capitalize(), config_data, 1 if body.enabled else 0),
        )

    logger.info("channel_config_updated", channel=channel_type, tenant_id=ctx.tenant_id, enabled=body.enabled)
    return {"channel": channel_type, "enabled": body.enabled, "updated_at": now}
