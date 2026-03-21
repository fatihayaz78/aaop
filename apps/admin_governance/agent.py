"""Admin & Governance agents — TenantAgent (M12) + ComplianceAgent (M17)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.admin_governance.config import AdminGovernanceConfig
from shared.agents.base_agent import AgentState, BaseAgent
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)


class TenantAgent(BaseAgent):
    """M12 — Tenant Self-Service. Haiku for admin operations."""

    app_name = "admin_governance"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = AdminGovernanceConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        role = state["tenant_context"].get("role", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "role": role,
            "action_type": input_data.get("action_type", "list"),
            "target_tenant": input_data.get("target_tenant", ""),
            "module_name": input_data.get("module_name", ""),
            "key_name": input_data.get("key_name", ""),
        }
        logger.info("tenant_context_loaded", tenant_id=tenant_id, role=role)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        role = ctx.get("role", "")
        action_type = ctx.get("action_type", "list")

        # Admin role check
        if role != self._config.required_role:
            return {"action": "unauthorized", "reason": f"Role '{role}' not authorized. Requires '{self._config.required_role}'."}

        # Haiku for admin operations
        response = await self.llm.invoke(
            f"Admin operation: {action_type} for tenant {ctx.get('tenant_id', '')}",
            severity=SeverityLevel.P3,
        )

        action_map = {
            "list": "list_tenants",
            "create": "create_tenant",
            "delete": "delete_tenant",
            "module_config": "update_module_config",
            "rotate_key": "rotate_api_key",
            "export_audit": "export_audit_log",
            "get_configs": "get_module_configs",
        }

        return {
            "action": action_map.get(action_type, action_type),
            "summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "unauthorized":
            return [{"tool": "unauthorized", "risk_level": "LOW"}]

        high_risk = {"delete_tenant", "rotate_api_key", "export_audit_log"}
        medium_risk = {"create_tenant", "update_module_config"}

        if action in high_risk:
            return [{"tool": action, "risk_level": "HIGH"}]
        if action in medium_risk:
            return [{"tool": action, "risk_level": "MEDIUM"}]
        return [{"tool": action, "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
        }


class ComplianceAgent(BaseAgent):
    """M17 — Compliance Dashboard. Sonnet for detailed analysis."""

    app_name = "admin_governance"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = AdminGovernanceConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "total_decisions": input_data.get("total_decisions", 0),
            "high_risk_count": input_data.get("high_risk_count", 0),
            "approval_rate": input_data.get("approval_rate", 100.0),
        }
        logger.info("compliance_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})

        # Sonnet for compliance analysis
        from apps.admin_governance.prompts import COMPLIANCE_ANALYSIS_PROMPT

        prompt = COMPLIANCE_ANALYSIS_PROMPT.format(
            tenant_id=ctx.get("tenant_id", ""),
            total_decisions=ctx.get("total_decisions", 0),
            high_risk_count=ctx.get("high_risk_count", 0),
            approval_rate=ctx.get("approval_rate", 100.0),
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        has_violations = ctx.get("high_risk_count", 0) > 0 and ctx.get("approval_rate", 100) < 95

        return {
            "action": "compliance_report",
            "summary": response["content"],
            "model_used": response["model"],
            "has_violations": has_violations,
            "total_decisions": ctx.get("total_decisions", 0),
            "high_risk_count": ctx.get("high_risk_count", 0),
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        return [{"tool": "generate_compliance_report", "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "has_violations": llm_resp.get("has_violations", False),
            "total_decisions": llm_resp.get("total_decisions", 0),
        }
