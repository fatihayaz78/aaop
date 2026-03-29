"""AlertRouterAgent — concrete BaseAgent with routing pipeline.

Pipeline: dedup → suppression → storm detection → severity-based routing.
Model routing: P0/P1 → Sonnet, P2/P3 → Haiku.
HIGH risk: route_to_pagerduty (P0), suppress_alert_storm.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.alert_center.config import AlertCenterConfig
from apps.alert_center.prompts import SYSTEM_PROMPT
import apps.alert_center.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)

# All 7 events this agent subscribes to
SUBSCRIBED_EVENTS = [
    "cdn_anomaly_detected",
    "incident_created",
    "rca_completed",
    "qoe_degradation",
    "live_event_starting",
    "churn_risk_detected",
    "scale_recommendation",
]


# ── BaseAgent-compatible tool wrappers ──────────────────────────


async def _check_dedup(tenant_id: str, source_app: str = "", event_type: str = "",
                       severity: str = "P3", **_: Any) -> dict:
    try:
        from backend.dependencies import _redis
        if _redis and _redis._client:
            hit = await tools.check_dedup(tenant_id, source_app, event_type, severity, _redis)
            return {"dedup_hit": hit}
    except Exception:
        pass
    return {"dedup_hit": False}


async def _get_routing_rules(tenant_id: str, event_type: str = "",
                             severity: str = "P3", **_: Any) -> dict:
    return await tools.get_routing_rules(tenant_id, event_type, severity)


async def _check_suppression(tenant_id: str, **_: Any) -> dict:
    suppressed = await tools.check_suppression(tenant_id)
    return {"suppressed": suppressed}


async def _detect_alert_storm(tenant_id: str, **_: Any) -> dict:
    is_storm = await tools.detect_alert_storm(tenant_id)
    return {"is_storm": is_storm}


async def _set_dedup_cache(tenant_id: str, source_app: str = "", event_type: str = "",
                           severity: str = "P3", **_: Any) -> dict:
    try:
        from backend.dependencies import _redis
        if _redis and _redis._client:
            await tools.set_dedup_cache(tenant_id, source_app, event_type, severity, _redis)
    except Exception:
        pass
    return {"status": "set"}


async def _route_to_slack(tenant_id: str, channel: str = "#ops-alerts", **_: Any) -> dict:
    return {"status": "sent", "channel": "slack", "target": channel}


async def _route_to_email(tenant_id: str, recipient: str = "ops@example.com", **_: Any) -> dict:
    return {"status": "sent", "channel": "email", "target": recipient}


async def _write_alert_to_db(tenant_id: str, **_: Any) -> dict:
    return {"status": "written", "tenant_id": tenant_id}


async def _route_to_pagerduty(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required", "channel": "pagerduty"}


async def _suppress_alert_storm(tenant_id: str, summary_message: str = "", **_: Any) -> dict:
    return await tools.suppress_alert_storm(tenant_id, summary_message)


# ── AlertRouterAgent ────────────────────────────────────────────


class AlertRouterAgent(BaseAgent):
    """M13 — Alert routing with dedup, storm detection, severity-based channels."""

    app_name = "alert_center"

    def __init__(self, **kwargs: Any) -> None:
        self._config = AlertCenterConfig()
        super().__init__(**kwargs)

    def subscribe_events(self) -> None:
        """Register all 7 event subscriptions."""
        for et in (EventType.CDN_ANOMALY_DETECTED, EventType.INCIDENT_CREATED,
                    EventType.RCA_COMPLETED, EventType.QOE_DEGRADATION,
                    EventType.LIVE_EVENT_STARTING, EventType.CHURN_RISK_DETECTED,
                    EventType.SCALE_RECOMMENDATION):
            self.event_bus.subscribe(et, self._on_event)

    async def _on_event(self, event: BaseEvent) -> None:
        try:
            payload = event.payload if isinstance(event.payload, dict) else {}
            payload["_source_event"] = event.event_type
            payload["severity"] = getattr(event, "severity", "P3")
            payload["source_app"] = getattr(event, "source_app", "")
            payload["title"] = payload.get("title", f"Alert: {event.event_type}")
            await self.invoke(tenant_id=event.tenant_id or "aaop_company", input_data=payload)
        except Exception as exc:
            logger.error("event_handler_error", app=self.app_name, event=event.event_type, error=str(exc))

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "check_dedup", "risk_level": "LOW", "func": _check_dedup},
            {"name": "get_routing_rules", "risk_level": "LOW", "func": _get_routing_rules},
            {"name": "check_suppression", "risk_level": "LOW", "func": _check_suppression},
            {"name": "detect_alert_storm", "risk_level": "LOW", "func": _detect_alert_storm},
            {"name": "set_dedup_cache", "risk_level": "LOW", "func": _set_dedup_cache},
            {"name": "route_to_slack", "risk_level": "MEDIUM", "func": _route_to_slack},
            {"name": "route_to_email", "risk_level": "MEDIUM", "func": _route_to_email},
            {"name": "write_alert_to_db", "risk_level": "MEDIUM", "func": _write_alert_to_db},
            {"name": "route_to_pagerduty", "risk_level": "HIGH", "func": _route_to_pagerduty},
            {"name": "suppress_alert_storm", "risk_level": "HIGH", "func": _suppress_alert_storm},
        ]

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity in ("P0", "P1"):
            return "claude-sonnet-4-20250514"
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Routing pipeline: dedup → suppression → storm → graph."""
        severity = input_data.get("severity", "P3")

        # Step 1: Dedup check
        if input_data.get("dedup_hit", False):
            return {
                "app": self.app_name, "tenant_id": tenant_id,
                "action": "dedup_drop", "reason": "Duplicate alert within dedup window",
                "channels": [], "approval_required": False, "severity": severity,
            }

        # Step 2: Suppression check
        suppressed = await tools.check_suppression(tenant_id)
        if suppressed:
            return {
                "app": self.app_name, "tenant_id": tenant_id,
                "action": "suppress_drop", "reason": "Alert suppressed during maintenance window",
                "channels": [], "approval_required": False, "severity": severity,
            }

        # Step 3: Storm detection
        is_storm = await tools.detect_alert_storm(tenant_id)
        if is_storm:
            return {
                "app": self.app_name, "tenant_id": tenant_id,
                "action": "storm_summary",
                "reason": f"Alert storm detected (>{self._config.storm_threshold_count} in {self._config.storm_window_seconds}s)",
                "channels": [], "approval_required": True, "severity": severity,
            }

        # Step 4: Normal routing — run full LangGraph cycle
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        """Add routing decision fields (channels, approval_required, severity)."""
        result = await super()._memory_update_node(state)

        input_data = state.get("input", {})
        severity = input_data.get("severity", "P3")

        # Determine channels based on severity
        channels: list[str] = []
        approval_required = False

        sev = SeverityLevel(severity) if severity in ("P0", "P1", "P2", "P3") else SeverityLevel.P3
        if sev == SeverityLevel.P0:
            channels = ["slack", "pagerduty"]
            approval_required = True
        elif sev in (SeverityLevel.P1, SeverityLevel.P2):
            channels = ["slack"]
        else:
            channels = ["email"]

        output = result.get("output", {})
        output["action"] = "route"
        output["channels"] = channels
        output["approval_required"] = approval_required
        output["severity"] = severity

        return {**result, "output": output}
