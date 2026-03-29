"""AI Lab agents — ExperimentationAgent (M10) + ModelGovernanceAgent (M14).

ExperimentationAgent: A/B test analysis with statistical significance.
ModelGovernanceAgent: LLM cost tracking + model governance.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.ai_lab.config import AILabConfig
from apps.ai_lab.prompts import EXPERIMENTATION_SYSTEM_PROMPT, MODEL_GOVERNANCE_SYSTEM_PROMPT
from apps.ai_lab.tools import analyze_statistical_significance
import apps.ai_lab.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _create_experiment(tenant_id: str, **_: Any) -> dict:
    return {"status": "created"}

async def _get_experiment_results(tenant_id: str, **_: Any) -> dict:
    return {"results": []}

async def _analyze_significance(tenant_id: str, **_: Any) -> dict:
    return {"p_value": 1.0, "is_significant": False}

async def _get_llm_cost_metrics(tenant_id: str, **_: Any) -> dict:
    return {"total_tokens": 0, "total_cost": 0.0}

async def _evaluate_model(tenant_id: str, **_: Any) -> dict:
    return {"status": "evaluated"}

async def _register_prompt_version(tenant_id: str, **_: Any) -> dict:
    return {"status": "registered"}

async def _update_model_config(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}

async def _switch_model_production(tenant_id: str, **_: Any) -> dict:
    return {"status": "approval_required"}


# ── ExperimentationAgent ────────────────────────────────────────

class ExperimentationAgent(BaseAgent):
    """M10 — AI Experimentation. Sonnet for statistical analysis."""

    app_name = "ai_lab"

    def __init__(self, **kwargs: Any) -> None:
        self._config = AILabConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "create_experiment", "risk_level": "LOW", "func": _create_experiment},
            {"name": "get_experiment_results", "risk_level": "LOW", "func": _get_experiment_results},
            {"name": "analyze_statistical_significance", "risk_level": "LOW", "func": _analyze_significance},
            {"name": "get_llm_cost_metrics", "risk_level": "LOW", "func": _get_llm_cost_metrics},
            {"name": "evaluate_model", "risk_level": "LOW", "func": _evaluate_model},
            {"name": "register_prompt_version", "risk_level": "MEDIUM", "func": _register_prompt_version},
            {"name": "update_model_config", "risk_level": "HIGH", "func": _update_model_config},
            {"name": "switch_model_production", "risk_level": "HIGH", "func": _switch_model_production},
        ]

    def get_system_prompt(self) -> str:
        return EXPERIMENTATION_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-sonnet-4-20250514"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        experiment_name = input_data.get("experiment_name", "")
        if not experiment_name:
            return {"app": self.app_name, "tenant_id": tenant_id, "action": "no_experiment",
                    "stats": {}}

        # Calculate statistical significance if results provided
        results = input_data.get("results", [])
        if len(results) >= 2:
            control = results[0]
            variant = results[1]
            stats = await analyze_statistical_significance(
                control.get("mean", 0), control.get("std", 1), control.get("n", 0),
                variant.get("mean", 0), variant.get("std", 1), variant.get("n", 0),
            )
        else:
            stats = {"p_value": 1.0, "is_significant": False, "effect_size": 0.0}

        input_data["_stats"] = stats
        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = "analyze_experiment"
        output["experiment_name"] = input_data.get("experiment_name", "")
        output["stats"] = input_data.get("_stats", {})

        return {**result, "output": output}


# ── ModelGovernanceAgent ────────────────────────────────────────

class ModelGovernanceAgent(BaseAgent):
    """M14 — ML Model Governance. Haiku for routine metric collection."""

    app_name = "ai_lab"

    def __init__(self, **kwargs: Any) -> None:
        self._config = AILabConfig()
        super().__init__(**kwargs)

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "get_llm_cost_metrics", "risk_level": "LOW", "func": _get_llm_cost_metrics},
            {"name": "evaluate_model", "risk_level": "LOW", "func": _evaluate_model},
            {"name": "register_prompt_version", "risk_level": "MEDIUM", "func": _register_prompt_version},
            {"name": "update_model_config", "risk_level": "HIGH", "func": _update_model_config},
            {"name": "switch_model_production", "risk_level": "HIGH", "func": _switch_model_production},
        ]

    def get_system_prompt(self) -> str:
        return MODEL_GOVERNANCE_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        action_type = input_data.get("action_type", "check_usage")
        budget_pct = input_data.get("budget_used_pct", 0.0)

        action = action_type
        if action_type == "switch_model":
            action = "switch_model_production"
        elif action_type == "update_config":
            action = "update_model_config"

        input_data["_mapped_action"] = action
        input_data["_budget_warning"] = budget_pct > self._config.token_budget_warn_pct

        return await super().invoke(tenant_id, input_data)

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = input_data.get("_mapped_action", "check_usage")
        output["budget_warning"] = input_data.get("_budget_warning", False)
        output["budget_used_pct"] = input_data.get("budget_used_pct", 0.0)
        output["model_name"] = input_data.get("model_name", "")

        return {**result, "output": output}
