"""LogAnalyzerAgent — extends BaseAgent with 4-step LangGraph cycle."""

from __future__ import annotations

from typing import Any

import structlog

from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


class LogAnalyzerAgent(BaseAgent):
    app_name = "log_analyzer"

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        """Load context from Redis cache and DuckDB."""
        tenant_id = state["tenant_context"].get("tenant_id", "")
        context: dict[str, Any] = {"tenant_id": tenant_id}
        logger.info("log_analyzer_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Call LLM to analyze metrics and generate summary."""
        context = state.get("context_data", {})
        metrics = context.get("metrics")
        anomalies = context.get("anomalies", [])

        if not metrics:
            return {"action": "no_data", "summary": "No metrics to analyze"}

        from apps.log_analyzer.prompts import ANALYSIS_PROMPT

        prompt = ANALYSIS_PROMPT.format(
            metrics_json=str(metrics),
            anomaly_count=len(anomalies),
            anomaly_details=str(anomalies),
            period_start=context.get("period_start", "N/A"),
            period_end=context.get("period_end", "N/A"),
            total_requests=metrics.get("total_requests", 0),
        )

        severity = SeverityLevel.P2
        for a in anomalies:
            if a.get("severity") == "P1":
                severity = SeverityLevel.P1
            elif a.get("severity") == "P0":
                severity = SeverityLevel.P0

        response = await self.llm.invoke(prompt, severity=severity)
        return {
            "action": "analyze_cdn_logs",
            "summary": response["content"],
            "model_used": response["model"],
            "severity": severity,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        """Execute analysis tools based on reasoning output."""
        llm_response = state.get("llm_response", {})
        return [{"tool": "analyze_cdn_logs", "result": llm_response.get("summary", "")}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        """Write results to DuckDB and publish events."""
        context = state.get("context_data", {})
        anomalies = context.get("anomalies", [])
        llm_response = state.get("llm_response", {})

        # Publish analysis_complete event
        tenant_id = context.get("tenant_id", "")
        event = BaseEvent(
            event_type=EventType.ANALYSIS_COMPLETE,
            tenant_id=tenant_id,
            source_app="log_analyzer",
            payload={"summary": llm_response.get("summary", "")},
        )
        await self.event_bus.publish(event)

        # If anomalies found, publish cdn_anomaly_detected
        if anomalies:
            severity = SeverityLevel.P2
            for a in anomalies:
                if a.get("severity") == "P1":
                    severity = SeverityLevel.P1
            anomaly_event = BaseEvent(
                event_type=EventType.CDN_ANOMALY_DETECTED,
                tenant_id=tenant_id,
                source_app="log_analyzer",
                severity=severity,
                payload={"anomalies": anomalies},
            )
            await self.event_bus.publish(anomaly_event)

        return {
            "action": llm_response.get("action", "analyze_cdn_logs"),
            "summary": llm_response.get("summary", ""),
            "anomaly_count": len(anomalies),
        }
