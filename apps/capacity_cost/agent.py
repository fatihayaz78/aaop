"""Capacity & Cost agents — CapacityAgent (M16) + AutomationAgent (M04)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.capacity_cost.config import CapacityCostConfig
from apps.capacity_cost.tools import detect_threshold_breach, forecast_capacity
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


class CapacityAgent(BaseAgent):
    """M16 — Capacity Planning. Sonnet for analysis. Publishes scale_recommendation."""

    app_name = "capacity_cost"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = CapacityCostConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})

        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "metric": input_data.get("metric", "bandwidth"),
            "current_pct": input_data.get("current_pct", 0.0),
            "trend": input_data.get("trend", "stable"),
            "live_event": input_data.get("live_event"),
        }
        logger.info("capacity_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        tenant_id = ctx.get("tenant_id", "")
        metric = ctx.get("metric", "bandwidth")
        current_pct = ctx.get("current_pct", 0.0)
        trend = ctx.get("trend", "stable")

        # Use Sonnet for capacity analysis
        from apps.capacity_cost.prompts import CAPACITY_ANALYSIS_PROMPT

        prompt = CAPACITY_ANALYSIS_PROMPT.format(
            tenant_id=tenant_id,
            metric=metric,
            current_pct=current_pct,
            warn_pct=self._config.warn_threshold_pct,
            crit_pct=self._config.crit_threshold_pct,
            trend=trend,
            horizon_hours=self._config.forecast_horizon_hours,
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        # Forecast
        fc = await forecast_capacity(
            tenant_id=tenant_id,
            metric=metric,
            current_pct=current_pct,
            trend=trend,
            horizon_hours=self._config.forecast_horizon_hours,
        )

        # Threshold check
        breach = await detect_threshold_breach(tenant_id, metric, current_pct)

        # Check for live event pre-scale
        live_event = ctx.get("live_event")
        needs_pre_scale = False
        if live_event:
            expected = live_event.get("expected_viewers", 0)
            needs_pre_scale = expected > 50_000

        action = "monitor"
        if breach and breach.level == "critical":
            action = "scale_critical"
        elif breach and breach.level == "warn":
            action = "scale_warn"
        elif needs_pre_scale:
            action = "pre_scale"

        return {
            "action": action,
            "summary": response["content"],
            "model_used": response["model"],
            "forecast": fc.model_dump(),
            "breach": breach.model_dump() if breach else None,
            "metric": metric,
            "current_pct": current_pct,
            "needs_pre_scale": needs_pre_scale,
            "live_event": live_event,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        results: list[dict[str, Any]] = []
        results.append({"tool": "write_forecast", "risk_level": "MEDIUM"})

        if action in ("scale_critical", "scale_warn"):
            results.append({"tool": "publish_scale_recommendation", "risk_level": "MEDIUM"})

        if action in ("scale_critical", "pre_scale"):
            results.append({"tool": "execute_scale_action", "risk_level": "HIGH"})

        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        tenant_id = ctx.get("tenant_id", "")
        action = llm_resp.get("action", "")
        scale_published = False

        # Publish scale_recommendation for threshold breaches
        if action in ("scale_critical", "scale_warn"):
            breach = llm_resp.get("breach", {})
            event = BaseEvent(
                event_type=EventType.SCALE_RECOMMENDATION,
                tenant_id=tenant_id,
                source_app="capacity_cost",
                severity=SeverityLevel.P1 if action == "scale_critical" else SeverityLevel.P2,
                payload={
                    "metric": llm_resp.get("metric", ""),
                    "current_pct": llm_resp.get("current_pct", 0.0),
                    "level": breach.get("level", "") if breach else "",
                    "message": breach.get("message", "") if breach else "",
                },
            )
            await self.event_bus.publish(event)
            scale_published = True

        return {
            "action": action,
            "metric": llm_resp.get("metric", ""),
            "current_pct": llm_resp.get("current_pct", 0.0),
            "scale_published": scale_published,
            "needs_pre_scale": llm_resp.get("needs_pre_scale", False),
        }


class AutomationAgent(BaseAgent):
    """M04 — Universal Automation. Haiku for routine. HIGH risk tools require approval."""

    app_name = "capacity_cost"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = CapacityCostConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "job_type": input_data.get("job_type", ""),
            "job_config": input_data.get("job_config", {}),
            "resource": input_data.get("resource", ""),
            "scale_factor": input_data.get("scale_factor", 1.0),
        }
        logger.info("automation_context_loaded", tenant_id=tenant_id, job_type=context["job_type"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        job_type = ctx.get("job_type", "")

        if not job_type:
            return {"action": "no_job", "reason": "No job_type specified"}

        # Use Haiku for routine automation
        response = await self.llm.invoke(
            f"Evaluate automation job: type={job_type}, config={ctx.get('job_config', {})}",
            severity=SeverityLevel.P3,  # Haiku
        )

        action = "create_job"
        if job_type == "scale":
            action = "scale_action"

        return {
            "action": action,
            "job_type": job_type,
            "summary": response["content"],
            "model_used": response["model"],
            "resource": ctx.get("resource", ""),
            "scale_factor": ctx.get("scale_factor", 1.0),
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "no_job":
            return [{"tool": "no_job", "risk_level": "LOW"}]

        if action == "scale_action":
            return [{"tool": "execute_scale_action", "risk_level": "HIGH"}]

        return [{"tool": "create_automation_job", "risk_level": "HIGH"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "job_type": llm_resp.get("job_type", ""),
            "resource": llm_resp.get("resource", ""),
            "scale_factor": llm_resp.get("scale_factor", 1.0),
        }
