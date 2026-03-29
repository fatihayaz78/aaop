"""Capacity & Cost agents — CapacityAgent (M16) + AutomationAgent (M04).

CapacityAgent: threshold monitoring + scale_recommendation event.
AutomationAgent: automation jobs + scale actions.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.capacity_cost.config import CapacityCostConfig
from apps.capacity_cost.prompts import AUTOMATION_SYSTEM_PROMPT, CAPACITY_SYSTEM_PROMPT
from apps.capacity_cost.tools import detect_threshold_breach, forecast_capacity
import apps.capacity_cost.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _get_current_metrics(tenant_id: str, **_: Any) -> list:
    return []

async def _forecast_capacity(tenant_id: str, **_: Any) -> dict:
    return {"status": "forecasted"}

async def _calculate_cost(tenant_id: str, **_: Any) -> dict:
    return {"status": "calculated"}

async def _detect_threshold_breach(tenant_id: str, **_: Any) -> dict:
    return {"status": "checked"}

async def _write_forecast(tenant_id: str, **_: Any) -> dict:
    return {"status": "written"}

async def _publish_scale_recommendation(tenant_id: str, **_: Any) -> dict:
    return {"status": "published"}

async def _create_automation_job(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}

async def _execute_scale_action(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}


# ── CapacityAgent ───────────────────────────────────────────────

class CapacityAgent(BaseAgent):
    """M16 — Capacity Planning. Sonnet for analysis."""

    app_name = "capacity_cost"

    def __init__(self, **kwargs: Any) -> None:
        self._config = CapacityCostConfig()
        super().__init__(**kwargs)

    def subscribe_events(self) -> None:
        """Register: live_event_starting (pre-scale calculation)."""
        self.event_bus.subscribe(EventType.LIVE_EVENT_STARTING, self._on_event)

    async def _on_event(self, event: BaseEvent) -> None:
        try:
            payload = event.payload if isinstance(event.payload, dict) else {}
            payload["_source_event"] = event.event_type
            payload["live_event"] = payload  # pass as live_event context
            await self.invoke(tenant_id=event.tenant_id or "aaop_company", input_data=payload)
        except Exception as exc:
            logger.error("event_handler_error", app=self.app_name, event=event.event_type, error=str(exc))

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_current_metrics", "risk_level": "LOW", "func": _get_current_metrics},
            {"name": "forecast_capacity", "risk_level": "LOW", "func": _forecast_capacity},
            {"name": "calculate_cost", "risk_level": "LOW", "func": _calculate_cost},
            {"name": "detect_threshold_breach", "risk_level": "LOW", "func": _detect_threshold_breach},
            {"name": "write_forecast", "risk_level": "MEDIUM", "func": _write_forecast},
            {"name": "publish_scale_recommendation", "risk_level": "MEDIUM", "func": _publish_scale_recommendation},
            {"name": "create_automation_job", "risk_level": "HIGH", "func": _create_automation_job},
            {"name": "execute_scale_action", "risk_level": "HIGH", "func": _execute_scale_action},
        ]

    def get_system_prompt(self) -> str:
        return CAPACITY_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        current_pct = input_data.get("current_pct", 0.0)
        metric = input_data.get("metric", "bandwidth")

        # Threshold detection
        breach = await detect_threshold_breach(tenant_id, metric, current_pct)
        live_event = input_data.get("live_event")
        needs_pre_scale = bool(live_event and live_event.get("expected_viewers", 0) > 50_000)

        action = "monitor"
        if breach and breach.level == "critical":
            action = "scale_critical"
        elif breach and breach.level == "warn":
            action = "scale_warn"
        elif needs_pre_scale:
            action = "pre_scale"

        input_data["_action"] = action
        input_data["_breach"] = breach.model_dump() if breach else None
        input_data["_needs_pre_scale"] = needs_pre_scale

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})
        action = input_data.get("_action", "monitor")
        breach = input_data.get("_breach")
        tenant_id = state.get("tenant_id", "")
        scale_published = False

        if action in ("scale_critical", "scale_warn"):
            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.SCALE_RECOMMENDATION,
                    tenant_id=tenant_id,
                    source_app="capacity_cost",
                    severity=SeverityLevel.P1 if action == "scale_critical" else SeverityLevel.P2,
                    payload={
                        "metric": input_data.get("metric", ""),
                        "current_pct": input_data.get("current_pct", 0.0),
                        "level": breach.get("level", "") if breach else "",
                        "message": breach.get("message", "") if breach else "",
                    },
                ))
                scale_published = True
            except Exception as exc:
                logger.warning("scale_recommendation_publish_failed", error=str(exc))

        output = result.get("output", {})
        output["action"] = action
        output["metric"] = input_data.get("metric", "")
        output["current_pct"] = input_data.get("current_pct", 0.0)
        output["scale_published"] = scale_published
        output["needs_pre_scale"] = input_data.get("_needs_pre_scale", False)

        return {**result, "output": output}


# ── AutomationAgent ─────────────────────────────────────────────

class AutomationAgent(BaseAgent):
    """M04 — Universal Automation. Haiku for routine."""

    app_name = "capacity_cost"

    def __init__(self, **kwargs: Any) -> None:
        self._config = CapacityCostConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_current_metrics", "risk_level": "LOW", "func": _get_current_metrics},
            {"name": "create_automation_job", "risk_level": "HIGH", "func": _create_automation_job},
            {"name": "execute_scale_action", "risk_level": "HIGH", "func": _execute_scale_action},
        ]

    def get_system_prompt(self) -> str:
        return AUTOMATION_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        job_type = input_data.get("job_type", "")
        if not job_type:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_job",
                    "job_type": "", "resource": "", "scale_factor": 1.0}

        action = "scale_action" if job_type == "scale" else "create_job"
        input_data["_action"] = action

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = input_data.get("_action", "create_job")
        output["job_type"] = input_data.get("job_type", "")
        output["resource"] = input_data.get("resource", "")
        output["scale_factor"] = input_data.get("scale_factor", 1.0)

        return {**result, "output": output}
