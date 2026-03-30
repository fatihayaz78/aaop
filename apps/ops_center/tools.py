"""Ops Center tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.ops_center.schemas import Incident, RCAResult
from shared.event_bus import EventBus, EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def get_incident_history(tenant_id: str, db: Any, limit: int = 20) -> list[dict]:
    """Get recent incidents. Risk: LOW."""
    return db.fetch_all(
        "SELECT * FROM shared_analytics.incidents WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        [tenant_id, limit],
    )


async def get_cdn_analysis(tenant_id: str, db: Any, limit: int = 5) -> list[dict]:
    """Read CDN analysis from DuckDB (written by log_analyzer). Risk: LOW."""
    return db.fetch_all(
        "SELECT * FROM shared_analytics.cdn_analysis WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        [tenant_id, limit],
    )


async def get_qoe_metrics(tenant_id: str, db: Any, limit: int = 5) -> list[dict]:
    """Read QoE metrics from DuckDB. Risk: LOW."""
    return db.fetch_all(
        "SELECT * FROM shared_analytics.qoe_metrics WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
        [tenant_id, limit],
    )


async def correlate_events(
    tenant_id: str,
    incident: Incident,
    cdn_data: list[dict],
    qoe_data: list[dict],
) -> dict[str, Any]:
    """Correlate CDN, QoE, and incident data. Risk: LOW."""
    correlation: dict[str, Any] = {
        "incident_id": incident.incident_id,
        "cdn_anomalies_found": len(cdn_data),
        "qoe_issues_found": len(qoe_data),
        "affected_services": incident.affected_services,
    }

    # Check CDN correlation
    if cdn_data:
        latest = cdn_data[0]
        correlation["cdn_error_rate"] = latest.get("error_rate")
        correlation["cdn_analysis_id"] = latest.get("analysis_id")

    # Check QoE correlation
    if qoe_data:
        correlation["qoe_affected_sessions"] = len(qoe_data)

    logger.info("events_correlated", tenant_id=tenant_id, correlation=correlation)
    return correlation


# ── MEDIUM risk tools ───────────────────────────────────


async def create_incident_record(tenant_id: str, incident: Incident, db: Any) -> str:
    """Write incident to DuckDB. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.incidents
        (incident_id, tenant_id, severity, title, status, source_app,
         correlation_ids, affected_svcs, metrics_at_time, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())""",
        [
            incident.incident_id, tenant_id, incident.severity,
            incident.title, incident.status, incident.source_app,
            str(incident.correlation_ids), str(incident.affected_services),
            str(incident.metrics_at_time),
        ],
    )
    logger.info("incident_created_in_db", tenant_id=tenant_id, incident_id=incident.incident_id)
    return incident.incident_id


async def update_incident_status(
    tenant_id: str, incident_id: str, status: str, db: Any
) -> None:
    """Update incident status. Risk: MEDIUM (auto+notify)."""
    db.execute(
        "UPDATE shared_analytics.incidents SET status = ?, updated_at = NOW() WHERE incident_id = ? AND tenant_id = ?",
        [status, incident_id, tenant_id],
    )
    logger.info("incident_status_updated", tenant_id=tenant_id, incident_id=incident_id, status=status)


async def trigger_rca(tenant_id: str, incident_id: str, event_bus: EventBus) -> None:
    """Trigger RCA for an incident — invokes RCAAgent for P0/P1. Risk: MEDIUM (auto+notify)."""
    logger.info("rca_triggered", tenant_id=tenant_id, incident_id=incident_id)

    try:
        # Check incident severity — only P0/P1 get RCA
        from backend.dependencies import _duckdb
        if _duckdb:
            rows = _duckdb.fetch_all(
                "SELECT severity FROM shared_analytics.incidents WHERE incident_id = ? AND tenant_id = ?",
                [incident_id, tenant_id],
            )
            if not rows:
                logger.info("rca_skip_no_incident", incident_id=incident_id)
                return
            severity = rows[0].get("severity", "P3")
            if severity not in ("P0", "P1"):
                logger.info("rca_skip_low_severity", incident_id=incident_id, severity=severity)
                return

        # Invoke RCAAgent
        from apps.ops_center.agent import RCAAgent
        agent = RCAAgent(event_bus=event_bus)
        await agent.invoke(
            tenant_id=tenant_id,
            input_data={"incident_id": incident_id, "severity": severity, "title": f"RCA for {incident_id}"},
        )
        logger.info("rca_agent_invoked", tenant_id=tenant_id, incident_id=incident_id)
    except Exception as exc:
        logger.error("rca_trigger_failed", incident_id=incident_id, error=str(exc))


async def send_slack_notification(tenant_id: str, message: str, channel: str = "#ops-alerts") -> dict:
    """Send Slack notification. Risk: MEDIUM (auto+notify)."""
    logger.info("slack_notification_sent", tenant_id=tenant_id, channel=channel)
    return {"status": "sent", "channel": channel}


async def publish_incident_created(
    tenant_id: str, incident: Incident, event_bus: EventBus
) -> None:
    """Publish incident_created event. Risk: MEDIUM."""
    event = BaseEvent(
        event_type=EventType.INCIDENT_CREATED,
        tenant_id=tenant_id,
        source_app="ops_center",
        severity=incident.severity,
        payload={
            "incident_id": incident.incident_id,
            "title": incident.title,
            "severity": incident.severity,
            "status": incident.status,
        },
    )
    await event_bus.publish(event)


async def publish_rca_completed(
    tenant_id: str, rca: RCAResult, event_bus: EventBus
) -> None:
    """Publish rca_completed event. Risk: MEDIUM."""
    event = BaseEvent(
        event_type=EventType.RCA_COMPLETED,
        tenant_id=tenant_id,
        source_app="ops_center",
        severity=SeverityLevel.P1,
        payload={
            "rca_id": rca.rca_id,
            "incident_id": rca.incident_id,
            "root_cause": rca.root_cause,
            "confidence": rca.confidence_score,
        },
    )
    await event_bus.publish(event)


# ── HIGH risk tools ─────────────────────────────────────


async def execute_remediation(tenant_id: str, action: str, target: str) -> dict:
    """Execute remediation action. Risk: HIGH (approval_required)."""
    logger.warning("remediation_requested", tenant_id=tenant_id, action=action, target=target)
    return {"status": "approval_required", "tenant_id": tenant_id, "action": action, "target": target}


async def escalate_to_oncall(tenant_id: str, incident_id: str, urgency: str = "high") -> dict:
    """Escalate to on-call engineer. Risk: HIGH (approval_required)."""
    logger.warning("oncall_escalation_requested", tenant_id=tenant_id, incident_id=incident_id)
    return {"status": "approval_required", "tenant_id": tenant_id, "incident_id": incident_id, "urgency": urgency}
