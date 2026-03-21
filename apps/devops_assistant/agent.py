"""DevOps Assistant agent — DevOpsAssistantAgent (M08)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.devops_assistant.config import DevOpsAssistantConfig
from shared.agents.base_agent import AgentState, BaseAgent
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)


class DevOpsAssistantAgent(BaseAgent):
    """M08 — AI DevOps Assistant. Sonnet for technical Q&A."""

    app_name = "devops_assistant"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = DevOpsAssistantConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "action_type": input_data.get("action_type", "diagnose"),
            "service": input_data.get("service", ""),
            "query": input_data.get("query", ""),
            "runbook_id": input_data.get("runbook_id", ""),
            "intent": input_data.get("intent", ""),
        }
        logger.info("devops_context_loaded", tenant_id=tenant_id, action=context["action_type"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        action_type = ctx.get("action_type", "diagnose")

        if action_type == "restart":
            return {
                "action": "restart_service",
                "service": ctx.get("service", ""),
            }

        if action_type == "runbook":
            return {
                "action": "execute_runbook",
                "runbook_id": ctx.get("runbook_id", ""),
            }

        if action_type == "suggest":
            return {
                "action": "suggest_command",
                "intent": ctx.get("intent", ""),
            }

        if action_type == "search_runbooks":
            return {
                "action": "search_runbooks",
                "query": ctx.get("query", ""),
            }

        # Default: diagnose
        service = ctx.get("service", "")
        if not service:
            return {"action": "no_service", "reason": "No service specified"}

        from apps.devops_assistant.prompts import DIAGNOSTIC_PROMPT

        prompt = DIAGNOSTIC_PROMPT.format(
            service=service, status="checking",
            incident_count=0, metrics_summary="N/A",
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        return {
            "action": "diagnose",
            "service": service,
            "summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "no_service":
            return [{"tool": "no_service", "risk_level": "LOW"}]
        if action == "restart_service":
            return [{"tool": "restart_service", "risk_level": "HIGH"}]
        if action == "execute_runbook":
            return [{"tool": "execute_runbook", "risk_level": "HIGH"}]
        if action == "suggest_command":
            return [{"tool": "suggest_command", "risk_level": "LOW"}]
        if action == "search_runbooks":
            return [{"tool": "search_runbooks", "risk_level": "LOW"}]
        return [{"tool": "check_service_health", "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "service": llm_resp.get("service", ""),
            "runbook_id": llm_resp.get("runbook_id", ""),
        }
