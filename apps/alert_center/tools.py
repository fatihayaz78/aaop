"""Alert Center tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

import time
from typing import Any

import structlog

from apps.alert_center.config import AlertCenterConfig
from apps.alert_center.schemas import Alert, compute_fingerprint
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)

# In-memory storm tracker (swap to Redis in production)
_storm_tracker: dict[str, list[float]] = {}


# ── LOW risk tools ──────────────────────────────────────


async def check_dedup(
    tenant_id: str, source_app: str, event_type: str, severity: str, redis: Any
) -> bool:
    """Check if alert is duplicate within 900s window. Risk: LOW."""
    fp = compute_fingerprint(tenant_id, source_app, event_type, severity)
    key = f"alert:dedup:{tenant_id}:{fp}"
    exists = await redis.exists(key)
    if exists:
        logger.info("alert_dedup_hit", tenant_id=tenant_id, fingerprint=fp)
    return bool(exists)


async def set_dedup_cache(
    tenant_id: str, source_app: str, event_type: str, severity: str, redis: Any
) -> None:
    """Set dedup cache entry with 900s TTL. Risk: LOW."""
    config = AlertCenterConfig()
    fp = compute_fingerprint(tenant_id, source_app, event_type, severity)
    key = f"alert:dedup:{tenant_id}:{fp}"
    await redis.set(key, "1", ttl=config.dedup_window_seconds)
    logger.info("alert_dedup_set", tenant_id=tenant_id, fingerprint=fp, ttl=config.dedup_window_seconds)


async def get_routing_rules(tenant_id: str, event_type: str, severity: str) -> dict[str, list[str]]:
    """Determine channels based on severity. Risk: LOW."""
    channels: list[str] = []
    approval_required = False

    sev = SeverityLevel(severity) if severity in ("P0", "P1", "P2", "P3") else SeverityLevel.P3

    if sev == SeverityLevel.P0:
        channels = ["slack", "pagerduty"]
        approval_required = True  # PagerDuty requires approval for P0
    elif sev == SeverityLevel.P1 or sev == SeverityLevel.P2:
        channels = ["slack"]
    else:
        channels = ["email"]

    return {"channels": channels, "approval_required": approval_required}


async def check_suppression(tenant_id: str) -> bool:
    """Check if alerts are suppressed (maintenance window). Risk: LOW."""
    # Placeholder — real implementation reads suppression_rules from SQLite
    return False


async def detect_alert_storm(tenant_id: str) -> bool:
    """Detect if alert storm is happening (>10 alerts in 5 min). Risk: LOW."""
    config = AlertCenterConfig()
    now = time.monotonic()
    key = tenant_id

    if key not in _storm_tracker:
        _storm_tracker[key] = []

    # Prune old entries
    _storm_tracker[key] = [t for t in _storm_tracker[key] if now - t < config.storm_window_seconds]
    _storm_tracker[key].append(now)

    is_storm = len(_storm_tracker[key]) > config.storm_threshold_count
    if is_storm:
        logger.warning("alert_storm_detected", tenant_id=tenant_id, count=len(_storm_tracker[key]))
    return is_storm


def reset_storm_tracker() -> None:
    """Reset storm tracker (for testing)."""
    _storm_tracker.clear()


# ── MEDIUM risk tools ───────────────────────────────────


async def route_to_slack(tenant_id: str, alert: Alert, channel: str = "#ops-alerts") -> dict:
    """Send alert to Slack. Risk: MEDIUM (auto+notify)."""
    logger.info("alert_routed_slack", tenant_id=tenant_id, alert_id=alert.alert_id, channel=channel)
    return {"status": "sent", "channel": "slack", "target": channel}


async def route_to_email(tenant_id: str, alert: Alert, recipient: str = "ops@example.com") -> dict:
    """Send alert via email. Risk: MEDIUM (auto+notify)."""
    logger.info("alert_routed_email", tenant_id=tenant_id, alert_id=alert.alert_id, recipient=recipient)
    return {"status": "sent", "channel": "email", "target": recipient}


async def write_alert_to_db(tenant_id: str, alert: Alert, db: Any) -> str:
    """Write alert to DuckDB alerts_sent. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.alerts_sent
        (alert_id, tenant_id, source_app, severity, channel, title, status, decision_id, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW())""",
        [
            alert.alert_id, tenant_id, alert.source_app, alert.severity,
            ",".join(alert.channels_routed), alert.title, alert.status, alert.decision_id,
        ],
    )
    logger.info("alert_written_to_db", tenant_id=tenant_id, alert_id=alert.alert_id)
    return alert.alert_id


# ── HIGH risk tools ─────────────────────────────────────


async def route_to_pagerduty(tenant_id: str, alert: Alert) -> dict:
    """Route alert to PagerDuty. Risk: HIGH (approval_required, P0 only)."""
    logger.warning("pagerduty_routing_requested", tenant_id=tenant_id, alert_id=alert.alert_id)
    return {"status": "approval_required", "channel": "pagerduty", "alert_id": alert.alert_id}


async def suppress_alert_storm(tenant_id: str, summary_message: str) -> dict:
    """Suppress alert storm and send single summary. Risk: HIGH (approval_required)."""
    logger.warning("alert_storm_suppression_requested", tenant_id=tenant_id)
    return {"status": "approval_required", "action": "suppress_storm", "summary": summary_message}
