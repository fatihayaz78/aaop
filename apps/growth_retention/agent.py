"""Growth & Retention agents — GrowthAgent (M18) + DataAnalystAgent (M03).

GrowthAgent: churn risk detection + event publishing.
DataAnalystAgent: NL→SQL on shared_analytics (read-only).
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.growth_retention.config import GrowthRetentionConfig
from apps.growth_retention.prompts import DATA_ANALYST_SYSTEM_PROMPT, GROWTH_SYSTEM_PROMPT
from apps.growth_retention.tools import calculate_churn_risk, validate_sql_query
import apps.growth_retention.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _calculate_churn_risk(tenant_id: str, **_: Any) -> dict:
    return {"status": "calculated"}

async def _get_qoe_correlation(tenant_id: str, **_: Any) -> list:
    return []

async def _get_cdn_impact(tenant_id: str, **_: Any) -> list:
    return []

async def _segment_customers(tenant_id: str, **_: Any) -> dict:
    return {"status": "segmented"}

async def _nl_to_sql_query(tenant_id: str, question: str = "", **_: Any) -> dict:
    return {"status": "queried"}

async def _get_growth_insights(tenant_id: str, **_: Any) -> list:
    return []

async def _validate_sql_query(tenant_id: str, **_: Any) -> dict:
    return {"valid": True}

async def _write_analysis_result(tenant_id: str, **_: Any) -> dict:
    return {"status": "written"}

async def _trigger_churn_alert(tenant_id: str, **_: Any) -> dict:
    return {"status": "triggered"}

async def _send_retention_campaign(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}


# ── GrowthAgent ─────────────────────────────────────────────────

class GrowthAgent(BaseAgent):
    """M18 — Customer Growth Intelligence. Sonnet for analysis."""

    app_name = "growth_retention"

    def __init__(self, **kwargs: Any) -> None:
        self._config = GrowthRetentionConfig()
        super().__init__(**kwargs)

    def subscribe_events(self) -> None:
        """Register: external_data_updated, analysis_complete."""
        self.event_bus.subscribe(EventType.EXTERNAL_DATA_UPDATED, self._on_event)
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETE, self._on_event)

    async def _on_event(self, event: BaseEvent) -> None:
        try:
            payload = event.payload if isinstance(event.payload, dict) else {}
            payload["_source_event"] = event.event_type
            await self.invoke(tenant_id=event.tenant_id or "aaop_company", input_data=payload)
        except Exception as exc:
            logger.error("event_handler_error", app=self.app_name, event=event.event_type, error=str(exc))

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "calculate_churn_risk", "risk_level": "LOW", "func": _calculate_churn_risk},
            {"name": "get_qoe_correlation", "risk_level": "LOW", "func": _get_qoe_correlation},
            {"name": "get_cdn_impact", "risk_level": "LOW", "func": _get_cdn_impact},
            {"name": "segment_customers", "risk_level": "LOW", "func": _segment_customers},
            {"name": "get_growth_insights", "risk_level": "LOW", "func": _get_growth_insights},
            {"name": "write_analysis_result", "risk_level": "MEDIUM", "func": _write_analysis_result},
            {"name": "trigger_churn_alert", "risk_level": "MEDIUM", "func": _trigger_churn_alert},
            {"name": "send_retention_campaign", "risk_level": "HIGH", "func": _send_retention_campaign},
        ]

    def get_system_prompt(self) -> str:
        return GROWTH_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        segment_id = input_data.get("segment_id", "")
        if not segment_id:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_segment",
                    "churn_risk": 0.0, "churn_alert_published": False}

        # Calculate churn risk
        qoe_data = input_data.get("qoe_data", [])
        avg_qoe = 5.0
        if qoe_data:
            scores = [d.get("quality_score", 5.0) for d in qoe_data]
            avg_qoe = sum(scores) / len(scores)

        cdn_data = input_data.get("cdn_data", [])
        cdn_error_rate = 0.0
        if cdn_data:
            rates = [d.get("error_rate", 0.0) for d in cdn_data]
            cdn_error_rate = sum(rates) / len(rates)

        churn = await calculate_churn_risk(
            tenant_id=tenant_id, segment_id=segment_id,
            qoe_avg=avg_qoe, cdn_error_rate=cdn_error_rate,
            retention_7d=input_data.get("retention_7d"),
            retention_30d=input_data.get("retention_30d"),
        )

        input_data["_churn_risk"] = churn.churn_risk
        input_data["_churn_factors"] = churn.factors

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})
        churn_risk = input_data.get("_churn_risk", 0.0)
        tenant_id = state.get("tenant_id", "")
        churn_alert_published = False

        if churn_risk > self._config.churn_risk_threshold:
            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.CHURN_RISK_DETECTED,
                    tenant_id=tenant_id,
                    source_app="growth_retention",
                    severity=SeverityLevel.P2,
                    payload={
                        "segment_id": input_data.get("segment_id", ""),
                        "churn_risk": churn_risk,
                        "factors": input_data.get("_churn_factors", {}),
                    },
                ))
                churn_alert_published = True
            except Exception as exc:
                logger.warning("churn_risk_publish_failed", error=str(exc))

        output = result.get("output", {})
        output["churn_risk"] = churn_risk
        output["churn_alert_published"] = churn_alert_published
        output["segment_id"] = input_data.get("segment_id", "")

        return {**result, "output": output}


# ── DataAnalystAgent ────────────────────────────────────────────

class DataAnalystAgent(BaseAgent):
    """M03 — AI Data Analyst. Sonnet for NL→SQL. Read-only shared_analytics."""

    app_name = "growth_retention"

    def __init__(self, **kwargs: Any) -> None:
        self._config = GrowthRetentionConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "nl_to_sql_query", "risk_level": "LOW", "func": _nl_to_sql_query},
            {"name": "validate_sql_query", "risk_level": "LOW", "func": _validate_sql_query},
            {"name": "get_growth_insights", "risk_level": "LOW", "func": _get_growth_insights},
            {"name": "write_analysis_result", "risk_level": "MEDIUM", "func": _write_analysis_result},
        ]

    def get_system_prompt(self) -> str:
        return DATA_ANALYST_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity == "P3":
            return "claude-haiku-4-5-20251001"
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        question = input_data.get("question", "")
        if not question:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_question",
                    "valid": False, "generated_sql": ""}
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        reasoning = state.get("reasoning", {})
        generated_sql = reasoning.get("reasoning", "").strip()

        valid, _ = validate_sql_query(generated_sql, self._config)

        output = result.get("output", {})
        output["action"] = "execute_query" if valid else "invalid_query"
        output["valid"] = valid
        output["generated_sql"] = generated_sql
        output["question"] = state.get("input", {}).get("question", "")

        return {**result, "output": output}
