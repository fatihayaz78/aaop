"""Live Intelligence agents — LiveEventAgent (M05) + ExternalDataAgent (M11).

LiveEventAgent: live_event_starting 30min before kickoff.
ExternalDataAgent: external_data_updated on data changes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from apps.live_intelligence.config import LiveIntelligenceConfig
from apps.live_intelligence.prompts import EXTERNAL_DATA_SYSTEM_PROMPT, LIVE_EVENT_SYSTEM_PROMPT
from apps.live_intelligence.schemas import LiveEvent
from apps.live_intelligence.tools import calculate_scale_factor
import apps.live_intelligence.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


def should_trigger_start(kickoff_time: datetime | None, trigger_minutes: int = 30) -> bool:
    """Check if live_event_starting should be published (30 min before kickoff)."""
    if kickoff_time is None:
        return False
    now = datetime.now(UTC)
    if kickoff_time.tzinfo is None:
        kickoff_time = kickoff_time.replace(tzinfo=UTC)
    time_until = kickoff_time - now
    return timedelta(0) <= time_until <= timedelta(minutes=trigger_minutes)


# ── Tool wrappers ───────────────────────────────────────────────

async def _get_upcoming_events(tenant_id: str, **_: Any) -> list:
    return []

async def _get_sportradar_data(tenant_id: str, match_id: str = "", **_: Any) -> dict:
    return {}

async def _get_drm_status(tenant_id: str, **_: Any) -> dict:
    return {"widevine": "healthy", "fairplay": "healthy", "playready": "healthy"}

async def _get_epg_schedule(tenant_id: str, **_: Any) -> list:
    return []

async def _calculate_scale_factor(tenant_id: str, **_: Any) -> dict:
    return {"scale_factor": 1.0}

async def _register_live_event(tenant_id: str, **_: Any) -> dict:
    return {"status": "registered"}

async def _update_event_status(tenant_id: str, event_id: str = "", status: str = "", **_: Any) -> dict:
    return {"status": "updated"}

async def _publish_event_start(tenant_id: str, **_: Any) -> dict:
    return {"status": "published"}

async def _publish_external_update(tenant_id: str, **_: Any) -> dict:
    return {"status": "published"}

async def _trigger_pre_scale(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}

async def _override_drm_fallback(tenant_id: str, provider: str = "", fallback_action: str = "", **_: Any) -> dict:
    return await tools.override_drm_fallback(tenant_id, provider, fallback_action)


# ── LiveEventAgent ──────────────────────────────────────────────

class LiveEventAgent(BaseAgent):
    """M05 — Live Event Monitor. Sonnet for analysis."""

    app_name = "live_intelligence"

    def __init__(self, **kwargs: Any) -> None:
        self._config = LiveIntelligenceConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_upcoming_events", "risk_level": "LOW", "func": _get_upcoming_events},
            {"name": "get_sportradar_data", "risk_level": "LOW", "func": _get_sportradar_data},
            {"name": "get_drm_status", "risk_level": "LOW", "func": _get_drm_status},
            {"name": "get_epg_schedule", "risk_level": "LOW", "func": _get_epg_schedule},
            {"name": "calculate_scale_factor", "risk_level": "LOW", "func": _calculate_scale_factor},
            {"name": "register_live_event", "risk_level": "MEDIUM", "func": _register_live_event},
            {"name": "update_event_status", "risk_level": "MEDIUM", "func": _update_event_status},
            {"name": "publish_event_start", "risk_level": "MEDIUM", "func": _publish_event_start},
            {"name": "publish_external_update", "risk_level": "MEDIUM", "func": _publish_external_update},
            {"name": "trigger_pre_scale", "risk_level": "HIGH", "func": _trigger_pre_scale},
            {"name": "override_drm_fallback", "risk_level": "HIGH", "func": _override_drm_fallback},
        ]

    def get_system_prompt(self) -> str:
        return LIVE_EVENT_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        event_data = input_data.get("event", {})
        if not event_data:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_event",
                    "event_start_published": False, "scale_factor": 1.0, "drm_healthy": True}

        event = LiveEvent(tenant_id=tenant_id, **event_data)
        trigger = should_trigger_start(event.kickoff_time, self._config.pre_event_trigger_minutes)
        scale = await calculate_scale_factor(tenant_id, event)

        input_data["_should_trigger"] = trigger
        input_data["_scale_factor"] = scale.scale_factor
        input_data["_event_data"] = event_data

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})
        trigger = input_data.get("_should_trigger", False)
        scale_factor = input_data.get("_scale_factor", 1.0)
        event_data = input_data.get("_event_data", {})
        tenant_id = state.get("tenant_id", "")

        action = "trigger_event_start" if trigger else "monitor_event"
        output = result.get("output", {})
        output["action"] = action
        output["event_start_published"] = trigger
        output["scale_factor"] = scale_factor
        output["drm_healthy"] = True

        if trigger:
            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.LIVE_EVENT_STARTING,
                    tenant_id=tenant_id,
                    source_app="live_intelligence",
                    severity=SeverityLevel.P2,
                    payload={
                        "event_name": event_data.get("event_name", ""),
                        "kickoff_time": str(event_data.get("kickoff_time", "")),
                        "expected_viewers": event_data.get("expected_viewers", 0),
                    },
                ))
            except Exception as exc:
                logger.warning("live_event_start_publish_failed", error=str(exc))

        return {**result, "output": output}


# ── ExternalDataAgent ──────────────────────────────────────��────

class ExternalDataAgent(BaseAgent):
    """M11 — External Data Connectors. Haiku for batch processing."""

    app_name = "live_intelligence"

    def __init__(self, **kwargs: Any) -> None:
        self._config = LiveIntelligenceConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_sportradar_data", "risk_level": "LOW", "func": _get_sportradar_data},
            {"name": "get_drm_status", "risk_level": "LOW", "func": _get_drm_status},
            {"name": "get_epg_schedule", "risk_level": "LOW", "func": _get_epg_schedule},
            {"name": "publish_external_update", "risk_level": "MEDIUM", "func": _publish_external_update},
        ]

    def get_system_prompt(self) -> str:
        return EXTERNAL_DATA_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        connector = input_data.get("connector", "")
        if not connector:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_connector",
                    "update_published": False}

        has_change = input_data.get("data") != input_data.get("previous_data")
        input_data["_has_change"] = has_change

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})
        has_change = input_data.get("_has_change", False)
        tenant_id = state.get("tenant_id", "")

        output = result.get("output", {})
        output["update_published"] = has_change
        output["connector"] = input_data.get("connector", "")

        if has_change:
            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.EXTERNAL_DATA_UPDATED,
                    tenant_id=tenant_id,
                    source_app="live_intelligence",
                    severity=SeverityLevel.P3,
                    payload={"connector": input_data.get("connector", ""), "data": input_data.get("data", {})},
                ))
            except Exception as exc:
                logger.warning("external_data_update_publish_failed", error=str(exc))

        return {**result, "output": output}
