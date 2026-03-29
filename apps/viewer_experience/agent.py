"""Viewer Experience agents — QoEAgent (M02) + ComplaintAgent (M09).

QoEAgent: QoE scoring + degradation event. ComplaintAgent: NLP categorization.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.viewer_experience.config import ViewerExperienceConfig
from apps.viewer_experience.prompts import COMPLAINT_SYSTEM_PROMPT, QOE_SYSTEM_PROMPT
from apps.viewer_experience.schemas import Complaint, QoESession
from apps.viewer_experience.tools import compute_qoe_score, is_session_deduped
import apps.viewer_experience.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)

SUBSCRIBED_EVENTS = ["analysis_complete", "live_event_starting"]


# ── Tool wrappers ───────────────────────────────────────────────

async def _score_qoe_session(tenant_id: str, **_: Any) -> dict:
    return {"status": "scored", "tenant_id": tenant_id}

async def _get_session_context(tenant_id: str, session_id: str = "", **_: Any) -> dict:
    return {"session_id": session_id}

async def _detect_qoe_anomaly(tenant_id: str, **_: Any) -> dict:
    return {"status": "checked"}

async def _search_similar_issues(tenant_id: str, **_: Any) -> list:
    return []

async def _categorize_complaint(tenant_id: str, content: str = "", **_: Any) -> dict:
    return {"status": "categorized"}

async def _find_related_complaints(tenant_id: str, **_: Any) -> list:
    return []

async def _write_qoe_metrics(tenant_id: str, **_: Any) -> dict:
    return {"status": "written"}

async def _write_complaint(tenant_id: str, **_: Any) -> dict:
    return {"status": "written"}

async def _trigger_qoe_alert(tenant_id: str, **_: Any) -> dict:
    return {"status": "triggered"}

async def _escalate_complaint(tenant_id: str, complaint_id: str = "", reason: str = "", **_: Any) -> dict:
    return await tools.escalate_complaint(tenant_id, complaint_id, reason)


# ── QoEAgent ────────────────────────────────────────────────────

class QoEAgent(BaseAgent):
    """M02 — QoE monitoring. P0/P1→Sonnet, others→Haiku."""

    app_name = "viewer_experience"

    def __init__(self, **kwargs: Any) -> None:
        self._config = ViewerExperienceConfig()
        super().__init__(**kwargs)

    def subscribe_events(self) -> None:
        """Register: analysis_complete, live_event_starting."""
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETE, self._on_event)
        self.event_bus.subscribe(EventType.LIVE_EVENT_STARTING, self._on_event)

    async def _on_event(self, event: BaseEvent) -> None:
        try:
            payload = event.payload if isinstance(event.payload, dict) else {}
            payload["_source_event"] = event.event_type
            await self.invoke(tenant_id=event.tenant_id or "aaop_company", input_data=payload)
        except Exception as exc:
            logger.error("event_handler_error", app=self.app_name, event=event.event_type, error=str(exc))

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "score_qoe_session", "risk_level": "LOW", "func": _score_qoe_session},
            {"name": "get_session_context", "risk_level": "LOW", "func": _get_session_context},
            {"name": "detect_qoe_anomaly", "risk_level": "LOW", "func": _detect_qoe_anomaly},
            {"name": "search_similar_issues", "risk_level": "LOW", "func": _search_similar_issues},
            {"name": "write_qoe_metrics", "risk_level": "MEDIUM", "func": _write_qoe_metrics},
            {"name": "trigger_qoe_alert", "risk_level": "MEDIUM", "func": _trigger_qoe_alert},
            {"name": "escalate_complaint", "risk_level": "HIGH", "func": _escalate_complaint},
        ]

    def get_system_prompt(self) -> str:
        return QOE_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity in ("P0", "P1"):
            return "claude-sonnet-4-20250514"
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        session_data = input_data.get("session", {})
        if not session_data:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_session"}

        session = QoESession(tenant_id=tenant_id, **session_data)

        if is_session_deduped(session.session_id, self._config.session_dedup_window_seconds):
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "dedup_skip"}

        score = compute_qoe_score(session)
        is_degraded = score < self._config.qoe_degradation_threshold
        input_data["_qoe_score"] = score
        input_data["_is_degraded"] = is_degraded

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})
        score = input_data.get("_qoe_score", 5.0)
        is_degraded = input_data.get("_is_degraded", False)
        tenant_id = state.get("tenant_id", "")

        action = "qoe_degradation" if is_degraded else "qoe_normal"
        output = result.get("output", {})
        output["action"] = action
        output["quality_score"] = score
        output["degradation_published"] = is_degraded

        if is_degraded:
            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.QOE_DEGRADATION,
                    tenant_id=tenant_id,
                    source_app="viewer_experience",
                    severity=SeverityLevel.P2,
                    payload={"quality_score": score, "session_id": input_data.get("session", {}).get("session_id", "")},
                ))
            except Exception as exc:
                logger.warning("qoe_degradation_publish_failed", error=str(exc))

        return {**result, "output": output}


# ── ComplaintAgent ──────────────────────────────────────────────

class ComplaintAgent(BaseAgent):
    """M09 — Complaint Analyzer. NLP category + sentiment + priority."""

    app_name = "viewer_experience"

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "categorize_complaint", "risk_level": "LOW", "func": _categorize_complaint},
            {"name": "find_related_complaints", "risk_level": "LOW", "func": _find_related_complaints},
            {"name": "write_complaint", "risk_level": "MEDIUM", "func": _write_complaint},
            {"name": "escalate_complaint", "risk_level": "HIGH", "func": _escalate_complaint},
        ]

    def get_system_prompt(self) -> str:
        return COMPLAINT_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        if not input_data.get("content"):
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_content"}
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        reasoning = state.get("reasoning", {})
        reasoning_text = reasoning.get("reasoning", "")

        category, sentiment, priority = _parse_complaint_nlp(reasoning_text)
        complaint = Complaint(
            tenant_id=state.get("tenant_id", ""),
            source=state.get("input", {}).get("source", ""),
            content=state.get("input", {}).get("content", ""),
            category=category, sentiment=sentiment, priority=priority,
        )

        output = result.get("output", {})
        output["complaint_id"] = complaint.id
        output["category"] = category
        output["sentiment"] = sentiment
        output["priority"] = priority

        return {**result, "output": output}


# ── NLP parser ──────────────────────────────────────────────────

def _parse_complaint_nlp(text: str) -> tuple[str, str, str]:
    """Parse LLM NLP output into category, sentiment, priority."""
    category = "other"
    sentiment = "neutral"
    priority = "P3"

    text_upper = text.upper()
    for cat in ("BUFFERING", "VIDEO_QUALITY", "AUDIO", "PLAYBACK", "LOGIN", "BILLING", "CONTENT"):
        if f"CATEGORY: {cat}" in text_upper or f"CATEGORY:{cat}" in text_upper:
            category = cat.lower()
            break

    for sent in ("VERY_NEGATIVE", "NEGATIVE", "NEUTRAL", "POSITIVE"):
        if f"SENTIMENT: {sent}" in text_upper or f"SENTIMENT:{sent}" in text_upper:
            sentiment = sent.lower()
            break

    for p in ("P0", "P1", "P2", "P3"):
        if f"PRIORITY: {p}" in text_upper or f"PRIORITY:{p}" in text_upper:
            priority = p
            break

    return category, sentiment, priority
