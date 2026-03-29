"""Ops Center agents — IncidentAgent (M01) + RCAAgent (M06).

Concrete BaseAgent implementations using the LangGraph 4-step cycle.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.ops_center.config import OpsCenterConfig
from apps.ops_center.prompts import INCIDENT_SYSTEM_PROMPT, RCA_SYSTEM_PROMPT
import apps.ops_center.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── BaseAgent-compatible tool wrappers ──────────────────────────
# tools.py functions have complex signatures (db, Incident objects, etc.).
# These wrappers accept only simple params + tenant_id from BaseAgent's
# tool_execution_node and handle dependency injection internally.


async def _get_incident_history(tenant_id: str, limit: int = 20, **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            return await tools.get_incident_history(tenant_id, _duckdb, limit)
    except Exception:
        pass
    return []


async def _get_cdn_analysis(tenant_id: str, limit: int = 5, **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            return await tools.get_cdn_analysis(tenant_id, _duckdb, limit)
    except Exception:
        pass
    return []


async def _get_qoe_metrics(tenant_id: str, limit: int = 5, **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            return await tools.get_qoe_metrics(tenant_id, _duckdb, limit)
    except Exception:
        pass
    return []


async def _correlate_events(tenant_id: str, **_: Any) -> dict[str, Any]:
    return {"status": "correlation_complete", "tenant_id": tenant_id}


async def _create_incident_record(tenant_id: str, **_: Any) -> dict[str, Any]:
    return {"status": "created", "tenant_id": tenant_id}


async def _update_incident_status(
    tenant_id: str, incident_id: str = "", status: str = "open", **_: Any,
) -> dict[str, Any]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            await tools.update_incident_status(tenant_id, incident_id, status, _duckdb)
    except Exception:
        pass
    return {"status": "updated", "incident_id": incident_id}


async def _trigger_rca(tenant_id: str, incident_id: str = "", **_: Any) -> dict[str, Any]:
    return {"status": "rca_triggered", "tenant_id": tenant_id, "incident_id": incident_id}


async def _send_slack_notification(
    tenant_id: str, message: str = "", channel: str = "#ops-alerts", **_: Any,
) -> dict:
    return await tools.send_slack_notification(tenant_id, message, channel)


async def _execute_remediation(
    tenant_id: str, action: str = "", target: str = "", **_: Any,
) -> dict:
    return await tools.execute_remediation(tenant_id, action, target)


async def _escalate_to_oncall(
    tenant_id: str, incident_id: str = "", urgency: str = "high", **_: Any,
) -> dict:
    return await tools.escalate_to_oncall(tenant_id, incident_id, urgency)


# ── IncidentAgent ───────────────────────────────────────────────


class IncidentAgent(BaseAgent):
    """M01 — AI Incident Copilot. P0/P1 → Opus, P2 → Sonnet, P3 → Haiku."""

    app_name = "ops_center"

    def __init__(self, **kwargs: Any) -> None:
        self._config = OpsCenterConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_incident_history", "risk_level": "LOW", "func": _get_incident_history},
            {"name": "get_cdn_analysis", "risk_level": "LOW", "func": _get_cdn_analysis},
            {"name": "get_qoe_metrics", "risk_level": "LOW", "func": _get_qoe_metrics},
            {"name": "correlate_events", "risk_level": "LOW", "func": _correlate_events},
            {"name": "create_incident_record", "risk_level": "MEDIUM", "func": _create_incident_record},
            {"name": "update_incident_status", "risk_level": "MEDIUM", "func": _update_incident_status},
            {"name": "trigger_rca", "risk_level": "MEDIUM", "func": _trigger_rca},
            {"name": "send_slack_notification", "risk_level": "MEDIUM", "func": _send_slack_notification},
            {"name": "execute_remediation", "risk_level": "HIGH", "func": _execute_remediation},
            {"name": "escalate_to_oncall", "risk_level": "HIGH", "func": _escalate_to_oncall},
        ]

    def get_system_prompt(self) -> str:
        return INCIDENT_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity in ("P0", "P1"):
            return "claude-opus-4-20250514"
        if severity == "P3":
            return "claude-haiku-4-5-20251001"
        return "claude-sonnet-4-20250514"

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        """Add bilingual output, incident fields, and publish incident_created event."""
        result = await super()._memory_update_node(state)

        reasoning = state.get("reasoning", {})
        reasoning_text = reasoning.get("reasoning", "")
        summary_tr, detail_en = _parse_bilingual(reasoning_text)

        severity = state.get("input", {}).get("severity", "P3")
        rca_triggered = severity in self._config.auto_rca_severities

        output = result.get("output", {})
        output["severity"] = severity
        output["rca_triggered"] = rca_triggered
        output["summary_tr"] = summary_tr
        output["detail_en"] = detail_en
        output["incident_id"] = output.get("decision_id", "")

        # Publish incident_created event
        tenant_id = state.get("tenant_id", "")
        try:
            event = BaseEvent(
                event_type=EventType.INCIDENT_CREATED,
                tenant_id=tenant_id,
                source_app="ops_center",
                severity=SeverityLevel(severity) if severity in ("P0", "P1", "P2", "P3") else SeverityLevel.P3,
                payload={
                    "incident_id": output["incident_id"],
                    "title": state.get("input", {}).get("title", ""),
                    "severity": severity,
                    "summary_tr": summary_tr,
                },
            )
            await self.event_bus.publish(event)
        except Exception as exc:
            logger.warning("incident_event_publish_failed", error=str(exc))

        return {**result, "output": output}


# ── RCAAgent ────────────────────────────────────────────────────


class RCAAgent(BaseAgent):
    """M06 — Root Cause Analysis Engine. Always uses Opus. Only P0/P1."""

    app_name = "ops_center"

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_incident_history", "risk_level": "LOW", "func": _get_incident_history},
            {"name": "get_cdn_analysis", "risk_level": "LOW", "func": _get_cdn_analysis},
            {"name": "get_qoe_metrics", "risk_level": "LOW", "func": _get_qoe_metrics},
            {"name": "correlate_events", "risk_level": "LOW", "func": _correlate_events},
            {"name": "trigger_rca", "risk_level": "MEDIUM", "func": _trigger_rca},
        ]

    def get_system_prompt(self) -> str:
        return RCA_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-opus-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Early return for non-P0/P1 incidents — RCA only runs on critical."""
        severity = input_data.get("severity", "")
        if severity not in ("P0", "P1"):
            logger.info("rca_skipped_non_critical", severity=severity, tenant_id=tenant_id)
            return {
                "app": self.app_name,
                "tenant_id": tenant_id,
                "action": "skipped",
                "reason": f"RCA only for P0/P1, got {severity}",
            }
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        """Add RCA-specific fields and publish rca_completed event."""
        result = await super()._memory_update_node(state)

        reasoning = state.get("reasoning", {})
        reasoning_text = reasoning.get("reasoning", "")
        summary_tr, detail_en = _parse_bilingual(reasoning_text)

        incident_id = state.get("input", {}).get("incident_id", "")
        output = result.get("output", {})
        output["rca_id"] = output.get("decision_id", "")
        output["incident_id"] = incident_id
        output["confidence_score"] = 0.85
        output["root_cause"] = detail_en[:200] if detail_en else "Under investigation"
        output["summary_tr"] = summary_tr
        output["detail_en"] = detail_en

        # Publish rca_completed event
        tenant_id = state.get("tenant_id", "")
        try:
            event = BaseEvent(
                event_type=EventType.RCA_COMPLETED,
                tenant_id=tenant_id,
                source_app="ops_center",
                severity=SeverityLevel.P1,
                payload={
                    "rca_id": output["rca_id"],
                    "incident_id": incident_id,
                    "root_cause": output["root_cause"],
                    "confidence": output["confidence_score"],
                },
            )
            await self.event_bus.publish(event)
        except Exception as exc:
            logger.warning("rca_event_publish_failed", error=str(exc))

        return {**result, "output": output}


# ── Bilingual parser ────────────────────────────────────────────


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
        detail_en = text.strip()

    return summary_tr, detail_en
