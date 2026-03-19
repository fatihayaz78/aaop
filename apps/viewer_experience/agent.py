"""Viewer Experience agents — QoEAgent (M02) + ComplaintAgent (M09)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.viewer_experience.config import ViewerExperienceConfig
from apps.viewer_experience.schemas import Complaint, QoESession
from apps.viewer_experience.tools import (
    compute_qoe_score,
    is_session_deduped,
)
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)

# Events this module subscribes to
SUBSCRIBED_EVENTS = ["analysis_complete", "live_event_starting"]


class QoEAgent(BaseAgent):
    """M02 — QoE monitoring. Sonnet for anomaly analysis, Haiku for batch scoring."""

    app_name = "viewer_experience"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = ViewerExperienceConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        session_data = input_data.get("session", {})
        session = QoESession(tenant_id=tenant_id, **session_data) if session_data else None

        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "session": session.model_dump() if session else None,
            "cdn_data": input_data.get("cdn_data", []),
            "live_events": input_data.get("live_events", []),
        }

        # Dedup check
        if session:
            context["deduped"] = is_session_deduped(
                session.session_id, self._config.session_dedup_window_seconds,
            )
        else:
            context["deduped"] = False

        logger.info("qoe_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})

        if ctx.get("deduped"):
            return {"action": "dedup_skip", "reason": "Session already processed within 5 min window"}

        session_data = ctx.get("session")
        if not session_data:
            return {"action": "no_session", "reason": "No session data provided"}

        session = QoESession(**session_data)
        score = compute_qoe_score(session)
        session.quality_score = score

        is_degraded = score < self._config.qoe_degradation_threshold

        if is_degraded:
            # Use Sonnet for anomaly analysis
            from apps.viewer_experience.prompts import QOE_ANALYSIS_PROMPT

            prompt = QOE_ANALYSIS_PROMPT.format(
                session_id=session.session_id, tenant_id=ctx["tenant_id"],
                quality_score=score, buffering_ratio=session.buffering_ratio,
                startup_time_ms=session.startup_time_ms, bitrate_avg=session.bitrate_avg,
                errors=session.errors, device_type=session.device_type, region=session.region,
            )
            response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)
            return {
                "action": "qoe_degradation",
                "quality_score": score,
                "summary": response["content"],
                "model_used": response["model"],
                "session": session.model_dump(),
            }

        return {
            "action": "qoe_normal",
            "quality_score": score,
            "session": session.model_dump(),
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action in ("dedup_skip", "no_session"):
            return [{"tool": action, "risk_level": "LOW"}]

        results: list[dict[str, Any]] = [
            {"tool": "write_qoe_metrics", "risk_level": "MEDIUM"},
        ]

        if action == "qoe_degradation":
            results.append({"tool": "trigger_qoe_alert", "risk_level": "MEDIUM"})

        state["context_data"]["scored_session"] = llm_resp.get("session")
        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")
        tenant_id = ctx.get("tenant_id", "")
        score = llm_resp.get("quality_score", 0.0)

        # Publish qoe_degradation if score < 2.5
        if action == "qoe_degradation":
            event = BaseEvent(
                event_type=EventType.QOE_DEGRADATION,
                tenant_id=tenant_id,
                source_app="viewer_experience",
                severity=SeverityLevel.P2,
                payload={
                    "quality_score": score,
                    "session_id": llm_resp.get("session", {}).get("session_id", ""),
                    "summary": llm_resp.get("summary", ""),
                },
            )
            await self.event_bus.publish(event)

        return {
            "action": action,
            "quality_score": score,
            "degradation_published": action == "qoe_degradation",
        }


class ComplaintAgent(BaseAgent):
    """M09 — Complaint Analyzer. NLP category + sentiment + priority."""

    app_name = "viewer_experience"

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "content": input_data.get("content", ""),
            "source": input_data.get("source", ""),
            "session_id": input_data.get("session_id"),
            "similar_ids": [],
        }
        logger.info("complaint_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        content = ctx.get("content", "")

        if not content:
            return {"action": "no_content", "reason": "No complaint content provided"}

        from apps.viewer_experience.prompts import COMPLAINT_ANALYSIS_PROMPT

        similar_summaries = f"Similar complaints: {len(ctx.get('similar_ids', []))}"

        prompt = COMPLAINT_ANALYSIS_PROMPT.format(
            content=content, source=ctx.get("source", ""),
            tenant_id=ctx["tenant_id"],
            similar_count=len(ctx.get("similar_ids", [])),
            similar_summaries=similar_summaries,
        )

        # Sonnet for complaint analysis
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        # Parse NLP result from LLM
        category, sentiment, priority = _parse_complaint_nlp(response["content"])

        return {
            "action": "categorize_complaint",
            "category": category,
            "sentiment": sentiment,
            "priority": priority,
            "summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})

        if llm_resp.get("action") == "no_content":
            return [{"tool": "no_content", "risk_level": "LOW"}]

        complaint = Complaint(
            tenant_id=ctx.get("tenant_id", ""),
            source=ctx.get("source", ""),
            content=ctx.get("content", ""),
            category=llm_resp.get("category", "other"),
            sentiment=llm_resp.get("sentiment", "neutral"),
            priority=llm_resp.get("priority", "P3"),
            related_session_id=ctx.get("session_id"),
        )

        state["context_data"]["complaint"] = complaint.model_dump()
        return [
            {"tool": "write_complaint", "risk_level": "MEDIUM", "complaint_id": complaint.id},
        ]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        complaint_data = ctx.get("complaint", {})

        return {
            "complaint_id": complaint_data.get("id", ""),
            "category": llm_resp.get("category", ""),
            "sentiment": llm_resp.get("sentiment", ""),
            "priority": llm_resp.get("priority", ""),
        }


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
