"""AI Lab agents — ExperimentationAgent (M10) + ModelGovernanceAgent (M14)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.ai_lab.config import AILabConfig
from apps.ai_lab.tools import analyze_statistical_significance
from shared.agents.base_agent import AgentState, BaseAgent
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)


class ExperimentationAgent(BaseAgent):
    """M10 — AI Experimentation. Sonnet for analysis."""

    app_name = "ai_lab"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = AILabConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "experiment_name": input_data.get("experiment_name", ""),
            "variants": input_data.get("variants", []),
            "metric": input_data.get("metric", ""),
            "results": input_data.get("results", []),
        }
        logger.info("experimentation_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        experiment_name = ctx.get("experiment_name", "")

        if not experiment_name:
            return {"action": "no_experiment", "reason": "No experiment specified"}

        results = ctx.get("results", [])
        if len(results) >= 2:
            control = results[0]
            variant = results[1]
            stats = await analyze_statistical_significance(
                control.get("mean", 0), control.get("std", 1), control.get("n", 0),
                variant.get("mean", 0), variant.get("std", 1), variant.get("n", 0),
            )
        else:
            stats = {"p_value": 1.0, "is_significant": False, "effect_size": 0.0}

        # Sonnet for analysis
        from apps.ai_lab.prompts import EXPERIMENT_ANALYSIS_PROMPT

        variants_str = "\n".join(
            f"  - {v.get('name', 'unknown')}: mean={v.get('mean', 0)}, n={v.get('n', 0)}"
            for v in results
        )
        prompt = EXPERIMENT_ANALYSIS_PROMPT.format(
            experiment_name=experiment_name,
            metric=ctx.get("metric", ""),
            variants_summary=variants_str or "No results yet",
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P2)

        return {
            "action": "analyze_experiment",
            "experiment_name": experiment_name,
            "summary": response["content"],
            "model_used": response["model"],
            "stats": stats,
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        if llm_resp.get("action") == "no_experiment":
            return [{"tool": "no_experiment", "risk_level": "LOW"}]
        return [{"tool": "create_experiment", "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "experiment_name": llm_resp.get("experiment_name", ""),
            "stats": llm_resp.get("stats", {}),
        }


class ModelGovernanceAgent(BaseAgent):
    """M14 — ML Model Governance. Haiku for routine metric collection."""

    app_name = "ai_lab"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = AILabConfig()

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "action_type": input_data.get("action_type", "check_usage"),
            "model_name": input_data.get("model_name", ""),
            "budget_used_pct": input_data.get("budget_used_pct", 0.0),
            "metrics": input_data.get("metrics", {}),
        }
        logger.info("governance_context_loaded", tenant_id=tenant_id)
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        action_type = ctx.get("action_type", "check_usage")
        budget_pct = ctx.get("budget_used_pct", 0.0)

        # Haiku for routine
        response = await self.llm.invoke(
            f"Model governance check: action={action_type}, budget={budget_pct}%",
            severity=SeverityLevel.P3,
        )

        budget_warning = budget_pct > self._config.token_budget_warn_pct
        if budget_warning:
            logger.warning("token_budget_exceeded_80pct", budget_pct=budget_pct)

        action = action_type
        if action_type == "switch_model":
            action = "switch_model_production"
        elif action_type == "update_config":
            action = "update_model_config"

        return {
            "action": action,
            "summary": response["content"],
            "model_used": response["model"],
            "budget_warning": budget_warning,
            "budget_used_pct": budget_pct,
            "model_name": ctx.get("model_name", ""),
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "switch_model_production":
            return [{"tool": "switch_model_production", "risk_level": "HIGH"}]
        if action == "update_model_config":
            return [{"tool": "update_model_config", "risk_level": "HIGH"}]
        return [{"tool": "get_llm_cost_metrics", "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        llm_resp = state.get("llm_response", {})
        return {
            "action": llm_resp.get("action", ""),
            "budget_warning": llm_resp.get("budget_warning", False),
            "budget_used_pct": llm_resp.get("budget_used_pct", 0.0),
            "model_name": llm_resp.get("model_name", ""),
        }
