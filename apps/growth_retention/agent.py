"""Growth & Retention agents — GrowthAgent (M18) + DataAnalystAgent (M03)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.growth_retention.config import GrowthRetentionConfig
from apps.growth_retention.tools import calculate_churn_risk, validate_sql_query
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


class GrowthAgent(BaseAgent):
    """M18 — Customer Growth Intelligence. Sonnet for analysis. Publishes churn_risk_detected."""

    app_name = "growth_retention"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = GrowthRetentionConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})

        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "segment_id": input_data.get("segment_id", ""),
            "qoe_data": input_data.get("qoe_data", []),
            "cdn_data": input_data.get("cdn_data", []),
            "retention_7d": input_data.get("retention_7d"),
            "retention_30d": input_data.get("retention_30d"),
        }
        logger.info("growth_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        segment_id = ctx.get("segment_id", "")
        tenant_id = ctx.get("tenant_id", "")

        if not segment_id:
            return {"action": "no_segment", "reason": "No segment_id provided"}

        # Calculate QoE average from data
        qoe_data = ctx.get("qoe_data", [])
        avg_qoe = 5.0
        if qoe_data:
            scores = [d.get("quality_score", 5.0) for d in qoe_data]
            avg_qoe = sum(scores) / len(scores)

        # CDN error rate
        cdn_data = ctx.get("cdn_data", [])
        cdn_error_rate = 0.0
        if cdn_data:
            rates = [d.get("error_rate", 0.0) for d in cdn_data]
            cdn_error_rate = sum(rates) / len(rates)

        # Use Sonnet for analysis
        from apps.growth_retention.prompts import CHURN_ANALYSIS_PROMPT

        prompt = CHURN_ANALYSIS_PROMPT.format(
            segment_id=segment_id,
            tenant_id=tenant_id,
            avg_qoe=f"{avg_qoe:.2f}",
            cdn_error_rate=f"{cdn_error_rate:.4f}",
            retention_7d=ctx.get("retention_7d", "N/A"),
            retention_30d=ctx.get("retention_30d", "N/A"),
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        # Calculate churn risk
        churn = await calculate_churn_risk(
            tenant_id=tenant_id,
            segment_id=segment_id,
            qoe_avg=avg_qoe,
            cdn_error_rate=cdn_error_rate,
            retention_7d=ctx.get("retention_7d"),
            retention_30d=ctx.get("retention_30d"),
        )

        return {
            "action": "churn_analysis",
            "summary": response["content"],
            "model_used": response["model"],
            "churn_risk": churn.churn_risk,
            "factors": churn.factors,
            "recommendation": churn.recommendation,
            "segment_id": segment_id,
            "avg_qoe": avg_qoe,
            "cdn_error_rate": cdn_error_rate,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "no_segment":
            return [{"tool": "no_segment", "risk_level": "LOW"}]

        results: list[dict[str, Any]] = []
        results.append({"tool": "write_analysis_result", "risk_level": "MEDIUM"})

        churn_risk = llm_resp.get("churn_risk", 0.0)
        if churn_risk > self._config.churn_risk_threshold:
            results.append({"tool": "trigger_churn_alert", "risk_level": "MEDIUM"})

        return results

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        tenant_id = ctx.get("tenant_id", "")
        churn_risk = llm_resp.get("churn_risk", 0.0)
        segment_id = llm_resp.get("segment_id", "")

        churn_alert_published = False

        # Publish churn_risk_detected if above threshold
        if churn_risk > self._config.churn_risk_threshold:
            event = BaseEvent(
                event_type=EventType.CHURN_RISK_DETECTED,
                tenant_id=tenant_id,
                source_app="growth_retention",
                severity=SeverityLevel.P2,
                payload={
                    "segment_id": segment_id,
                    "churn_risk": churn_risk,
                    "factors": llm_resp.get("factors", {}),
                },
            )
            await self.event_bus.publish(event)
            churn_alert_published = True

        return {
            "action": llm_resp.get("action", ""),
            "churn_risk": churn_risk,
            "churn_alert_published": churn_alert_published,
            "segment_id": segment_id,
            "recommendation": llm_resp.get("recommendation", ""),
        }


class DataAnalystAgent(BaseAgent):
    """M03 — AI Data Analyst. Sonnet for NL→SQL. Read-only shared_analytics only."""

    app_name = "growth_retention"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = GrowthRetentionConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "question": input_data.get("question", ""),
        }
        logger.info("data_analyst_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        question = ctx.get("question", "")
        tenant_id = ctx.get("tenant_id", "")

        if not question:
            return {"action": "no_question", "reason": "No question provided"}

        # Use Sonnet for NL→SQL
        from apps.growth_retention.prompts import NL_TO_SQL_PROMPT

        prompt = NL_TO_SQL_PROMPT.format(
            question=question,
            tenant_id=tenant_id,
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        generated_sql = response["content"].strip()
        # Validate SQL
        valid, reason = validate_sql_query(generated_sql, self._config)

        return {
            "action": "execute_query" if valid else "invalid_query",
            "question": question,
            "generated_sql": generated_sql,
            "model_used": response["model"],
            "valid": valid,
            "validation_reason": reason,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action in ("no_question", "invalid_query"):
            return [{"tool": action, "risk_level": "LOW"}]

        return [{"tool": "nl_to_sql_query", "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "question": llm_resp.get("question", ""),
            "generated_sql": llm_resp.get("generated_sql", ""),
            "valid": llm_resp.get("valid", False),
        }
