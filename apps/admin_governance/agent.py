"""Admin & Governance agents — TenantAgent (M12) + ComplianceAgent (M17).

TenantAgent: admin CRUD with role check. ComplianceAgent: audit + violations.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.admin_governance.config import AdminGovernanceConfig
from apps.admin_governance.prompts import COMPLIANCE_SYSTEM_PROMPT, TENANT_SYSTEM_PROMPT
import apps.admin_governance.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _list_tenants(tenant_id: str, **_: Any) -> list:
    return []

async def _get_module_configs(tenant_id: str, **_: Any) -> list:
    return []

async def _get_audit_log(tenant_id: str, **_: Any) -> list:
    return []

async def _get_usage_stats(tenant_id: str, **_: Any) -> dict:
    return {}

async def _generate_compliance_report(tenant_id: str, **_: Any) -> dict:
    return {"status": "generated"}

async def _create_tenant(tenant_id: str, **_: Any) -> dict:
    return {"status": "created"}

async def _update_module_config(tenant_id: str, **_: Any) -> dict:
    return {"status": "updated"}

async def _rotate_api_key(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}

async def _delete_tenant(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}

async def _export_audit_log(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}


# ── TenantAgent ─────────────────────────────────────────────────

class TenantAgent(BaseAgent):
    """M12 — Tenant Self-Service. Haiku for admin operations."""

    app_name = "admin_governance"

    def __init__(self, **kwargs: Any) -> None:
        self._config = AdminGovernanceConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "list_tenants", "risk_level": "LOW", "func": _list_tenants},
            {"name": "get_module_configs", "risk_level": "LOW", "func": _get_module_configs},
            {"name": "get_audit_log", "risk_level": "LOW", "func": _get_audit_log},
            {"name": "get_usage_stats", "risk_level": "LOW", "func": _get_usage_stats},
            {"name": "create_tenant", "risk_level": "MEDIUM", "func": _create_tenant},
            {"name": "update_module_config", "risk_level": "MEDIUM", "func": _update_module_config},
            {"name": "rotate_api_key", "risk_level": "HIGH", "func": _rotate_api_key},
            {"name": "delete_tenant", "risk_level": "HIGH", "func": _delete_tenant},
            {"name": "export_audit_log", "risk_level": "HIGH", "func": _export_audit_log},
        ]

    def get_system_prompt(self) -> str:
        return TENANT_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        role = input_data.get("_role", "")
        if role != self._config.required_role:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "unauthorized",
                    "reason": f"Role '{role}' not authorized. Requires '{self._config.required_role}'."}

        action_type = input_data.get("action_type", "list")
        action_map = {
            "list": "list_tenants", "create": "create_tenant", "delete": "delete_tenant",
            "module_config": "update_module_config", "rotate_key": "rotate_api_key",
            "export_audit": "export_audit_log", "get_configs": "get_module_configs",
        }
        input_data["_mapped_action"] = action_map.get(action_type, action_type)

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = input_data.get("_mapped_action", "list_tenants")

        return {**result, "output": output}

    async def run(self, tenant_context: Any, input_data: dict[str, Any] | None = None) -> Any:
        """Override run to inject role from tenant_context."""
        data = input_data or {}
        data["_role"] = getattr(tenant_context, "role", "")
        return await super().run(tenant_context, data)


# ── ComplianceAgent ─────────────────────────────────────────────

class ComplianceAgent(BaseAgent):
    """M17 — Compliance Dashboard. Sonnet for detailed analysis."""

    app_name = "admin_governance"

    def __init__(self, **kwargs: Any) -> None:
        self._config = AdminGovernanceConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "generate_compliance_report", "risk_level": "LOW", "func": _generate_compliance_report},
            {"name": "get_audit_log", "risk_level": "LOW", "func": _get_audit_log},
            {"name": "get_usage_stats", "risk_level": "LOW", "func": _get_usage_stats},
        ]

    def get_system_prompt(self) -> str:
        return COMPLIANCE_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        high_risk_count = input_data.get("high_risk_count", 0)
        approval_rate = input_data.get("approval_rate", 100.0)
        has_violations = high_risk_count > 0 and approval_rate < 95

        output = result.get("output", {})
        output["action"] = "compliance_report"
        output["has_violations"] = has_violations
        output["total_decisions"] = input_data.get("total_decisions", 0)

        return {**result, "output": output}
