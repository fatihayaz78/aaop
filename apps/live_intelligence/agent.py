"""Live Intelligence agents — LiveEventAgent (M05) + ExternalDataAgent (M11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from apps.live_intelligence.config import LiveIntelligenceConfig
from apps.live_intelligence.schemas import DRMStatus, LiveEvent
from apps.live_intelligence.tools import calculate_scale_factor
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


def should_trigger_start(kickoff_time: datetime | None, trigger_minutes: int = 30) -> bool:
    """Check if live_event_starting should be published (30 min before kickoff)."""
    if kickoff_time is None:
        return False
    now = datetime.now(UTC)
    # Make kickoff_time timezone-aware if it isn't
    if kickoff_time.tzinfo is None:
        kickoff_time = kickoff_time.replace(tzinfo=UTC)
    time_until = kickoff_time - now
    return timedelta(0) <= time_until <= timedelta(minutes=trigger_minutes)


class LiveEventAgent(BaseAgent):
    """M05 — Live Event Monitor. Sonnet for analysis. Publishes live_event_starting."""

    app_name = "live_intelligence"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = LiveIntelligenceConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        event_data = input_data.get("event", {})

        event = LiveEvent(tenant_id=tenant_id, **event_data) if event_data else None
        drm_data = input_data.get("drm_status", {})
        drm = DRMStatus(tenant_id=tenant_id, **drm_data) if drm_data else DRMStatus(tenant_id=tenant_id)

        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "event": event.model_dump() if event else None,
            "drm_status": drm.model_dump(),
            "qoe_data": input_data.get("qoe_data", []),
            "incidents": input_data.get("incidents", []),
        }

        # Check if we should trigger start event
        if event and event.kickoff_time:
            context["should_trigger_start"] = should_trigger_start(
                event.kickoff_time, self._config.pre_event_trigger_minutes,
            )
        else:
            context["should_trigger_start"] = False

        logger.info("live_event_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        event_data = ctx.get("event")

        if not event_data:
            return {"action": "no_event", "reason": "No event data provided"}

        event = LiveEvent(**event_data)

        # Use Sonnet for live event analysis
        from apps.live_intelligence.prompts import LIVE_EVENT_ANALYSIS_PROMPT

        drm = DRMStatus(**ctx.get("drm_status", {}))
        prompt = LIVE_EVENT_ANALYSIS_PROMPT.format(
            event_name=event.event_name, sport=event.sport,
            competition=event.competition,
            kickoff_time=event.kickoff_time,
            expected_viewers=event.expected_viewers,
            drm_status=f"Widevine={drm.widevine}, FairPlay={drm.fairplay}, PlayReady={drm.playready}",
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        # Calculate scale recommendation
        scale = await calculate_scale_factor(ctx["tenant_id"], event)

        action = "monitor_event"
        if ctx.get("should_trigger_start"):
            action = "trigger_event_start"

        return {
            "action": action,
            "summary": response["content"],
            "model_used": response["model"],
            "scale_factor": scale.scale_factor,
            "scale_reason": scale.reason,
            "event": event_data,
            "drm_healthy": drm.all_healthy,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "no_event":
            return [{"tool": "no_event", "risk_level": "LOW"}]

        results: list[dict[str, Any]] = []

        if action == "trigger_event_start":
            results.append({"tool": "publish_event_start", "risk_level": "MEDIUM"})

        if llm_resp.get("scale_factor", 1.0) > 1.0:
            results.append({"tool": "trigger_pre_scale", "risk_level": "HIGH"})

        if not llm_resp.get("drm_healthy", True):
            results.append({"tool": "override_drm_fallback", "risk_level": "HIGH"})

        results.append({"tool": "register_live_event", "risk_level": "MEDIUM"})
        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        tenant_id = ctx.get("tenant_id", "")
        action = llm_resp.get("action", "")

        # Publish live_event_starting if triggered
        if action == "trigger_event_start":
            event_data = llm_resp.get("event", {})
            event = BaseEvent(
                event_type=EventType.LIVE_EVENT_STARTING,
                tenant_id=tenant_id,
                source_app="live_intelligence",
                severity=SeverityLevel.P2,
                payload={
                    "event_id": event_data.get("event_id", ""),
                    "event_name": event_data.get("event_name", ""),
                    "kickoff_time": str(event_data.get("kickoff_time", "")),
                    "expected_viewers": event_data.get("expected_viewers", 0),
                },
            )
            await self.event_bus.publish(event)

        return {
            "action": action,
            "event_start_published": action == "trigger_event_start",
            "scale_factor": llm_resp.get("scale_factor", 1.0),
            "drm_healthy": llm_resp.get("drm_healthy", True),
        }


class ExternalDataAgent(BaseAgent):
    """M11 — External Data Connectors. Haiku for batch processing. Publishes external_data_updated."""

    app_name = "live_intelligence"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = LiveIntelligenceConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "connector": input_data.get("connector", ""),
            "data": input_data.get("data", {}),
            "previous_data": input_data.get("previous_data", {}),
        }
        logger.info("external_data_context_loaded", tenant_id=tenant_id, connector=context["connector"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        connector = ctx.get("connector", "")

        if not connector:
            return {"action": "no_connector", "reason": "No connector specified"}

        # Use Haiku for batch data processing
        response = await self.llm.invoke(
            f"Process {connector} data update: {ctx.get('data', {})}",
            severity=SeverityLevel.P3,  # Haiku
        )

        # Determine if data changed significantly
        has_change = ctx.get("data") != ctx.get("previous_data")

        return {
            "action": "process_update" if has_change else "no_change",
            "connector": connector,
            "summary": response["content"],
            "model_used": response["model"],
            "has_significant_change": has_change,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action in ("no_connector", "no_change"):
            return [{"tool": action, "risk_level": "LOW"}]

        return [{"tool": "publish_external_update", "risk_level": "MEDIUM"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        tenant_id = ctx.get("tenant_id", "")

        if llm_resp.get("has_significant_change"):
            event = BaseEvent(
                event_type=EventType.EXTERNAL_DATA_UPDATED,
                tenant_id=tenant_id,
                source_app="live_intelligence",
                severity=SeverityLevel.P3,
                payload={
                    "connector": llm_resp.get("connector", ""),
                    "data": ctx.get("data", {}),
                },
            )
            await self.event_bus.publish(event)

        return {
            "action": llm_resp.get("action", ""),
            "connector": llm_resp.get("connector", ""),
            "update_published": llm_resp.get("has_significant_change", False),
        }
