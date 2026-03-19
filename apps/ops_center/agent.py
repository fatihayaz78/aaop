"""Ops Center agents — IncidentAgent (M01) + RCAAgent (M06)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.ops_center.config import OpsCenterConfig
from apps.ops_center.prompts import (
    INCIDENT_ANALYSIS_PROMPT,
    RCA_ANALYSIS_PROMPT,
)
from apps.ops_center.schemas import Incident, RCAResult
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


class IncidentAgent(BaseAgent):
    """M01 — AI Incident Copilot. P0/P1 → Opus, P2/P3 → Sonnet."""

    app_name = "ops_center"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = OpsCenterConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        """Load context from input data and build context summary."""
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "event_type": input_data.get("event_type", "manual"),
            "severity": input_data.get("severity", "P3"),
            "payload": input_data.get("payload", {}),
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "source_app": input_data.get("source_app", ""),
            "affected_services": input_data.get("affected_services", []),
            "correlation_ids": input_data.get("correlation_ids", []),
            "metrics": input_data.get("metrics", {}),
            "cdn_data": input_data.get("cdn_data", []),
            "recent_incidents": input_data.get("recent_incidents", []),
        }
        logger.info("incident_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Call LLM with severity-based model routing."""
        ctx = state.get("context_data", {})
        severity_str = ctx.get("severity", "P3")
        severity = SeverityLevel(severity_str) if severity_str in ("P0", "P1", "P2", "P3") else SeverityLevel.P3

        context_summary = (
            f"CDN data points: {len(ctx.get('cdn_data', []))}, "
            f"Recent incidents: {len(ctx.get('recent_incidents', []))}, "
            f"Metrics: {ctx.get('metrics', {})}"
        )

        prompt = INCIDENT_ANALYSIS_PROMPT.format(
            event_type=ctx.get("event_type", "unknown"),
            tenant_id=ctx.get("tenant_id", ""),
            severity=severity_str,
            payload=str(ctx.get("payload", {})),
            context_summary=context_summary,
        )

        # P0/P1 → Opus, P2/P3 → Sonnet
        response = await self.llm.invoke(prompt, severity=severity)
        return {
            "action": "analyze_incident",
            "summary": response["content"],
            "model_used": response["model"],
            "severity": severity_str,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        """Create incident record based on analysis."""
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        summary = llm_resp.get("summary", "")

        # Parse TR/EN from LLM output
        summary_tr, detail_en = _parse_bilingual(summary)

        severity_str = ctx.get("severity", "P3")
        incident = Incident(
            tenant_id=ctx.get("tenant_id", ""),
            severity=SeverityLevel(severity_str) if severity_str in ("P0", "P1", "P2", "P3") else SeverityLevel.P3,
            title=ctx.get("title", "") or f"Auto-detected {ctx.get('event_type', 'incident')}",
            description=ctx.get("description", ""),
            source_app=ctx.get("source_app", ""),
            affected_services=ctx.get("affected_services", []),
            metrics_at_time=ctx.get("metrics", {}),
            correlation_ids=ctx.get("correlation_ids", []),
            summary_tr=summary_tr,
            detail_en=detail_en,
        )

        results: list[dict[str, Any]] = [
            {"tool": "create_incident_record", "incident_id": incident.incident_id, "risk_level": "MEDIUM"},
        ]

        # Auto-trigger RCA for P0/P1
        if severity_str in self._config.auto_rca_severities:
            results.append({"tool": "trigger_rca", "incident_id": incident.incident_id, "risk_level": "MEDIUM"})

        state["context_data"]["incident"] = incident.model_dump()
        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        """Publish incident_created event."""
        ctx = state.get("context_data", {})
        incident_data = ctx.get("incident", {})
        tenant_id = ctx.get("tenant_id", "")

        # Publish incident_created
        event = BaseEvent(
            event_type=EventType.INCIDENT_CREATED,
            tenant_id=tenant_id,
            source_app="ops_center",
            severity=SeverityLevel(incident_data.get("severity", "P3")),
            payload={
                "incident_id": incident_data.get("incident_id", ""),
                "title": incident_data.get("title", ""),
                "severity": incident_data.get("severity", "P3"),
                "summary_tr": incident_data.get("summary_tr", ""),
            },
        )
        await self.event_bus.publish(event)

        severity = incident_data.get("severity", "P3")
        rca_triggered = severity in self._config.auto_rca_severities

        return {
            "incident_id": incident_data.get("incident_id", ""),
            "severity": severity,
            "rca_triggered": rca_triggered,
            "summary_tr": incident_data.get("summary_tr", ""),
            "detail_en": incident_data.get("detail_en", ""),
        }


class RCAAgent(BaseAgent):
    """M06 — Root Cause Analysis Engine. Always uses Opus. Only P0/P1."""

    app_name = "ops_center"

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        """Load incident data and correlated CDN/QoE data."""
        input_data = state.get("context_data", {})
        tenant_id = state["tenant_context"].get("tenant_id", "")
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "incident_id": input_data.get("incident_id", ""),
            "severity": input_data.get("severity", "P1"),
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "affected_services": input_data.get("affected_services", []),
            "metrics": input_data.get("metrics", {}),
            "cdn_data": input_data.get("cdn_data", []),
            "recent_incidents": input_data.get("recent_incidents", []),
        }
        logger.info("rca_context_loaded", tenant_id=tenant_id, incident_id=context["incident_id"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Always use Opus for RCA."""
        ctx = state.get("context_data", {})

        prompt = RCA_ANALYSIS_PROMPT.format(
            incident_id=ctx.get("incident_id", ""),
            severity=ctx.get("severity", "P1"),
            title=ctx.get("title", ""),
            description=ctx.get("description", ""),
            affected_services=ctx.get("affected_services", []),
            metrics=ctx.get("metrics", {}),
            cdn_data=str(ctx.get("cdn_data", [])),
            recent_incidents=str(ctx.get("recent_incidents", [])),
        )

        # RCA always uses Opus (P0/P1 only)
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P0)
        return {
            "action": "perform_rca",
            "summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        """Build RCA result."""
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        summary = llm_resp.get("summary", "")
        summary_tr, detail_en = _parse_bilingual(summary)

        rca = RCAResult(
            incident_id=ctx.get("incident_id", ""),
            tenant_id=ctx.get("tenant_id", ""),
            root_cause=detail_en[:200] if detail_en else "Under investigation",
            summary_tr=summary_tr,
            detail_en=detail_en,
            confidence_score=0.85,
            correlation_data={
                "cdn_data_points": len(ctx.get("cdn_data", [])),
                "recent_incidents": len(ctx.get("recent_incidents", [])),
            },
        )

        state["context_data"]["rca"] = rca.model_dump()
        return [{"tool": "rca_complete", "rca_id": rca.rca_id, "risk_level": "MEDIUM"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        """Publish rca_completed event."""
        ctx = state.get("context_data", {})
        rca_data = ctx.get("rca", {})
        tenant_id = ctx.get("tenant_id", "")

        event = BaseEvent(
            event_type=EventType.RCA_COMPLETED,
            tenant_id=tenant_id,
            source_app="ops_center",
            severity=SeverityLevel.P1,
            payload={
                "rca_id": rca_data.get("rca_id", ""),
                "incident_id": rca_data.get("incident_id", ""),
                "root_cause": rca_data.get("root_cause", ""),
                "confidence": rca_data.get("confidence_score", 0),
            },
        )
        await self.event_bus.publish(event)

        return {
            "rca_id": rca_data.get("rca_id", ""),
            "incident_id": rca_data.get("incident_id", ""),
            "root_cause": rca_data.get("root_cause", ""),
            "summary_tr": rca_data.get("summary_tr", ""),
            "detail_en": rca_data.get("detail_en", ""),
            "confidence_score": rca_data.get("confidence_score", 0),
        }


def _parse_bilingual(text: str) -> tuple[str, str]:
    """Parse LLM output into Turkish summary and English detail."""
    summary_tr = ""
    detail_en = ""

    if "TÜRKÇE ÖZET:" in text:
        parts = text.split("TÜRKÇE ÖZET:", 1)
        rest = parts[1] if len(parts) > 1 else ""
        if "ENGLISH DETAIL:" in rest:
            tr_part, en_part = rest.split("ENGLISH DETAIL:", 1)
            summary_tr = tr_part.strip()
            detail_en = en_part.strip()
        elif "ROOT CAUSE:" in rest:
            tr_part, en_part = rest.split("ROOT CAUSE:", 1)
            summary_tr = tr_part.strip()
            detail_en = en_part.strip()
        else:
            summary_tr = rest.strip()
    else:
        # Fallback: use entire text as English detail
        detail_en = text.strip()

    return summary_tr, detail_en
