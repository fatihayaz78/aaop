"""DevOps Assistant agent — DevOpsAssistantAgent (M08).

P0/P1→Sonnet, others→Haiku. Infrastructure tools → HIGH risk approval.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.devops_assistant.config import DevOpsAssistantConfig
from apps.devops_assistant.prompts import DEVOPS_SYSTEM_PROMPT
import apps.devops_assistant.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _check_service_health(tenant_id: str, service: str = "", **_: Any) -> dict:
    return {"service": service, "status": "healthy"}

async def _get_deployment_history(tenant_id: str, **_: Any) -> list:
    return []

async def _search_runbooks(tenant_id: str, query: str = "", **_: Any) -> list:
    return []

async def _get_platform_metrics(tenant_id: str, **_: Any) -> dict:
    return {}

async def _suggest_command(tenant_id: str, intent: str = "", **_: Any) -> dict:
    return {"command": "", "intent": intent}

async def _create_deployment_record(tenant_id: str, **_: Any) -> dict:
    return {"status": "created"}

async def _execute_runbook(tenant_id: str, runbook_id: str = "", **_: Any) -> dict:
    return {"status": "approval_required", "runbook_id": runbook_id}

async def _restart_service(tenant_id: str, service: str = "", **_: Any) -> dict:
    return {"status": "approval_required", "service": service}


# ── DevOpsAssistantAgent ────────────────────────────────────────

class DevOpsAssistantAgent(BaseAgent):
    """M08 — AI DevOps Assistant. P0/P1→Sonnet, others→Haiku."""

    app_name = "devops_assistant"

    def __init__(self, **kwargs: Any) -> None:
        self._config = DevOpsAssistantConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "check_service_health", "risk_level": "LOW", "func": _check_service_health},
            {"name": "get_deployment_history", "risk_level": "LOW", "func": _get_deployment_history},
            {"name": "search_runbooks", "risk_level": "LOW", "func": _search_runbooks},
            {"name": "get_platform_metrics", "risk_level": "LOW", "func": _get_platform_metrics},
            {"name": "suggest_command", "risk_level": "LOW", "func": _suggest_command},
            {"name": "create_deployment_record", "risk_level": "MEDIUM", "func": _create_deployment_record},
            {"name": "execute_runbook", "risk_level": "HIGH", "func": _execute_runbook},
            {"name": "restart_service", "risk_level": "HIGH", "func": _restart_service},
        ]

    def get_system_prompt(self) -> str:
        return DEVOPS_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        if severity == "P3":
            return "claude-haiku-4-5-20251001"
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        action_type = input_data.get("action_type", "diagnose")

        action_map = {
            "restart": "restart_service",
            "runbook": "execute_runbook",
            "suggest": "suggest_command",
            "search_runbooks": "search_runbooks",
        }

        if action_type in action_map:
            input_data["_mapped_action"] = action_map[action_type]
            return await super().invoke(tenant_id, input_data)

        # Default: diagnose
        service = input_data.get("service", "")
        if not service:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_service",
                    "service": "", "runbook_id": ""}

        input_data["_mapped_action"] = "diagnose"
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = input_data.get("_mapped_action", "diagnose")
        output["service"] = input_data.get("service", "")
        output["runbook_id"] = input_data.get("runbook_id", "")

        return {**result, "output": output}
