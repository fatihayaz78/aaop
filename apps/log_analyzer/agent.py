"""LogAnalyzerAgent — concrete BaseAgent with LangGraph 4-step cycle.

Model routing: P0 CDN critical → Opus, batch/P3 → Haiku, default → Sonnet.
Events: cdn_anomaly_detected (error_rate > threshold), analysis_complete (every run).
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.log_analyzer.config import LogAnalyzerConfig
from apps.log_analyzer.prompts import SYSTEM_PROMPT
import apps.log_analyzer.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── BaseAgent-compatible tool wrappers ──────────────────────────


async def _list_log_projects(tenant_id: str, **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _sqlite
        if _sqlite:
            return await tools.list_log_projects(tenant_id, _sqlite)
    except Exception:
        pass
    return []


async def _get_analysis_history(tenant_id: str, limit: int = 20, **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            return await tools.get_analysis_history(tenant_id, _duckdb, limit)
    except Exception:
        pass
    return []


async def _search_similar_anomalies(tenant_id: str, anomaly_type: str = "", **_: Any) -> list[dict]:
    try:
        from backend.dependencies import _duckdb
        if _duckdb:
            return await tools.search_similar_anomalies(tenant_id, anomaly_type, _duckdb)
    except Exception:
        pass
    return []


async def _fetch_s3_logs(tenant_id: str, bucket: str = "", prefix: str = "", **_: Any) -> list:
    return await tools.fetch_s3_logs(tenant_id, bucket, prefix)


async def _parse_akamai_logs(tenant_id: str, content: str = "", **_: Any) -> list:
    return await tools.parse_akamai_logs(tenant_id, content)


async def _calculate_error_metrics(tenant_id: str, **_: Any) -> dict:
    return {"status": "calculated", "tenant_id": tenant_id}


async def _detect_anomalies(tenant_id: str, **_: Any) -> list[dict]:
    return []


async def _generate_charts(tenant_id: str, **_: Any) -> dict:
    return {"status": "charts_generated", "tenant_id": tenant_id}


async def _write_analysis_to_db(tenant_id: str, **_: Any) -> dict:
    return {"status": "written", "tenant_id": tenant_id}


async def _generate_docx_report(tenant_id: str, **_: Any) -> dict:
    return {"status": "report_generated", "tenant_id": tenant_id}


async def _trigger_cdn_alert(tenant_id: str, **_: Any) -> dict:
    return {"status": "alert_triggered", "tenant_id": tenant_id}


async def _purge_cdn_cache(tenant_id: str, paths: list[str] | None = None, **_: Any) -> dict:
    return await tools.purge_cdn_cache(tenant_id, paths or [])


# ── LogAnalyzerAgent ────────────────────────────────────────────


class LogAnalyzerAgent(BaseAgent):
    """M07 — CDN Log Analyzer. P0→Opus, P3→Haiku, default→Sonnet."""

    app_name = "log_analyzer"

    def __init__(self, **kwargs: Any) -> None:
        self._config = LogAnalyzerConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "list_log_projects", "risk_level": "LOW", "func": _list_log_projects},
            {"name": "get_analysis_history", "risk_level": "LOW", "func": _get_analysis_history},
            {"name": "search_similar_anomalies", "risk_level": "LOW", "func": _search_similar_anomalies},
            {"name": "fetch_s3_logs", "risk_level": "LOW", "func": _fetch_s3_logs},
            {"name": "parse_akamai_logs", "risk_level": "LOW", "func": _parse_akamai_logs},
            {"name": "calculate_error_metrics", "risk_level": "LOW", "func": _calculate_error_metrics},
            {"name": "detect_anomalies", "risk_level": "LOW", "func": _detect_anomalies},
            {"name": "generate_charts", "risk_level": "LOW", "func": _generate_charts},
            {"name": "write_analysis_to_db", "risk_level": "MEDIUM", "func": _write_analysis_to_db},
            {"name": "generate_docx_report", "risk_level": "MEDIUM", "func": _generate_docx_report},
            {"name": "trigger_cdn_alert", "risk_level": "MEDIUM", "func": _trigger_cdn_alert},
            {"name": "purge_cdn_cache", "risk_level": "HIGH", "func": _purge_cdn_cache},
        ]

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity == "P0":
            return "claude-opus-4-20250514"
        if severity == "P3":
            return "claude-haiku-4-5-20251001"
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Early return if no metrics provided."""
        if not input_data.get("metrics"):
            return {
                "app": self.app_name,
                "tenant_id": tenant_id,
                "action": "no_data",
                "summary": "No metrics to analyze",
            }
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        """Add anomaly count, publish analysis_complete + cdn_anomaly_detected."""
        result = await super()._memory_update_node(state)

        input_data = state.get("input", {})
        anomalies = input_data.get("anomalies", [])
        reasoning = state.get("reasoning", {})

        output = result.get("output", {})
        output["anomaly_count"] = len(anomalies)
        output["summary"] = reasoning.get("reasoning", "")

        tenant_id = state.get("tenant_id", "")

        # Publish analysis_complete on every successful analysis
        try:
            await self.event_bus.publish(BaseEvent(
                event_type=EventType.ANALYSIS_COMPLETE,
                tenant_id=tenant_id,
                source_app="log_analyzer",
                payload={"summary": output["summary"][:200]},
            ))
        except Exception as exc:
            logger.warning("analysis_complete_publish_failed", error=str(exc))

        # Publish cdn_anomaly_detected if anomalies found
        if anomalies:
            severity = SeverityLevel.P2
            for a in anomalies:
                if a.get("severity") == "P0":
                    severity = SeverityLevel.P0
                elif a.get("severity") == "P1" and severity != SeverityLevel.P0:
                    severity = SeverityLevel.P1

            try:
                await self.event_bus.publish(BaseEvent(
                    event_type=EventType.CDN_ANOMALY_DETECTED,
                    tenant_id=tenant_id,
                    source_app="log_analyzer",
                    severity=severity,
                    payload={"anomalies": anomalies},
                ))
            except Exception as exc:
                logger.warning("cdn_anomaly_publish_failed", error=str(exc))

        return {**result, "output": output}
