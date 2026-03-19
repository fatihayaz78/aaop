"""AlertRouterAgent — routes alerts based on severity, dedup, storm detection."""

from __future__ import annotations

from typing import Any

import structlog

from apps.alert_center.config import AlertCenterConfig
from apps.alert_center.schemas import Alert, compute_fingerprint
from apps.alert_center.tools import check_suppression, detect_alert_storm
from shared.agents.base_agent import AgentState, BaseAgent
from shared.schemas.base_event import SeverityLevel

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


class AlertRouterAgent(BaseAgent):
    """M13 — Alert routing with dedup, storm detection, severity-based channels."""

    app_name = "alert_center"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = AlertCenterConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        """Load event data and build routing context."""
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "event_type": input_data.get("event_type", ""),
            "severity": input_data.get("severity", "P3"),
            "source_app": input_data.get("source_app", ""),
            "title": input_data.get("title", ""),
            "payload": input_data.get("payload", {}),
            "dedup_hit": input_data.get("dedup_hit", False),
        }
        logger.info("alert_context_loaded", tenant_id=tenant_id, event_type=context["event_type"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Determine routing decision: dedup, suppress, storm, or route."""
        ctx = state.get("context_data", {})
        tenant_id = ctx.get("tenant_id", "")
        severity_str = ctx.get("severity", "P3")
        severity = SeverityLevel(severity_str) if severity_str in ("P0", "P1", "P2", "P3") else SeverityLevel.P3

        # Step 1: Dedup check
        if ctx.get("dedup_hit", False):
            return {"action": "dedup_drop", "reason": "Duplicate alert within dedup window"}

        # Step 2: Suppression check
        suppressed = await check_suppression(tenant_id)
        if suppressed:
            return {"action": "suppress_drop", "reason": "Alert suppressed during maintenance window"}

        # Step 3: Storm detection
        is_storm = await detect_alert_storm(tenant_id)
        if is_storm:
            return {
                "action": "storm_summary",
                "reason": f"Alert storm detected (>{self._config.storm_threshold_count} in {self._config.storm_window_seconds}s)",
                "approval_required": True,
            }

        # Step 4: Route based on severity
        channels: list[str] = []
        approval_required = False

        if severity == SeverityLevel.P0:
            channels = ["slack", "pagerduty"]
            approval_required = True
        elif severity == SeverityLevel.P1 or severity == SeverityLevel.P2:
            channels = ["slack"]
        else:
            channels = ["email"]

        # Use Haiku for routing decision, Sonnet for message generation
        response = await self.llm.invoke(
            f"Route alert: {ctx.get('title', '')} [{severity_str}] from {ctx.get('source_app', '')}",
            severity=SeverityLevel.P3,  # Haiku for routing
        )

        return {
            "action": "route",
            "channels": channels,
            "approval_required": approval_required,
            "severity": severity_str,
            "llm_summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        """Build alert and routing results."""
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "route")

        if action in ("dedup_drop", "suppress_drop"):
            return [{"tool": action, "risk_level": "LOW", "result": "dropped"}]

        if action == "storm_summary":
            return [{"tool": "suppress_alert_storm", "risk_level": "HIGH", "result": "approval_required"}]

        # Build alert
        severity_str = ctx.get("severity", "P3")
        severity = SeverityLevel(severity_str) if severity_str in ("P0", "P1", "P2", "P3") else SeverityLevel.P3
        channels = llm_resp.get("channels", ["email"])

        alert = Alert(
            tenant_id=ctx.get("tenant_id", ""),
            source_app=ctx.get("source_app", ""),
            event_type=ctx.get("event_type", ""),
            severity=severity,
            title=ctx.get("title", ""),
            message=llm_resp.get("llm_summary", ""),
            channels_routed=channels,
            fingerprint=compute_fingerprint(
                ctx.get("tenant_id", ""),
                ctx.get("source_app", ""),
                ctx.get("event_type", ""),
                severity_str,
            ),
        )

        results: list[dict[str, Any]] = []
        for ch in channels:
            risk = "HIGH" if ch == "pagerduty" else "MEDIUM"
            results.append({"tool": f"route_to_{ch}", "risk_level": risk, "alert_id": alert.alert_id})

        results.append({"tool": "write_alert_to_db", "risk_level": "MEDIUM", "alert_id": alert.alert_id})

        state["context_data"]["alert"] = alert.model_dump()
        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        """Return routing decision summary."""
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        alert_data = ctx.get("alert", {})

        return {
            "action": llm_resp.get("action", "route"),
            "alert_id": alert_data.get("alert_id", ""),
            "channels": llm_resp.get("channels", []),
            "approval_required": llm_resp.get("approval_required", False),
            "severity": ctx.get("severity", "P3"),
            "reason": llm_resp.get("reason", ""),
        }
