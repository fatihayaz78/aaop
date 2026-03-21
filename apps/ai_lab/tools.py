"""AI Lab tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

import math
from typing import Any

import structlog

from apps.ai_lab.config import AILabConfig
from apps.ai_lab.schemas import (
    Experiment,
    ExperimentResult,
    LLMCostMetrics,
    ModelEvaluation,
    PromptVersion,
)

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def create_experiment(
    tenant_id: str, name: str, variants: list[dict[str, Any]], metric: str,
) -> Experiment:
    """Create a new A/B experiment. Risk: LOW."""
    config = AILabConfig()
    capped = variants[: config.experiment_max_variants]
    exp = Experiment(
        tenant_id=tenant_id, name=name, variants=capped, metric=metric, status="draft",
    )
    logger.info("experiment_created", tenant_id=tenant_id, experiment_id=exp.experiment_id)
    return exp


async def get_experiment_results(
    tenant_id: str, experiment_id: str, results_data: list[dict[str, Any]],
) -> list[ExperimentResult]:
    """Get experiment results. Risk: LOW."""
    return [ExperimentResult(experiment_id=experiment_id, **r) for r in results_data]


async def analyze_statistical_significance(
    control_mean: float,
    control_std: float,
    control_n: int,
    variant_mean: float,
    variant_std: float,
    variant_n: int,
) -> dict[str, Any]:
    """Calculate p-value and CI for A/B test. Risk: LOW."""
    config = AILabConfig()

    # Two-sample z-test approximation
    if control_n == 0 or variant_n == 0:
        return {"p_value": 1.0, "is_significant": False, "effect_size": 0.0}

    se = math.sqrt((control_std**2 / control_n) + (variant_std**2 / variant_n))
    if se == 0:
        return {"p_value": 1.0, "is_significant": False, "effect_size": 0.0}

    z = abs(variant_mean - control_mean) / se
    # Approximate p-value from z-score (two-tailed)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))

    effect_size = variant_mean - control_mean
    ci_lower = effect_size - 1.96 * se
    ci_upper = effect_size + 1.96 * se

    return {
        "p_value": round(p_value, 6),
        "is_significant": p_value < config.significance_threshold,
        "effect_size": round(effect_size, 4),
        "confidence_interval": (round(ci_lower, 4), round(ci_upper, 4)),
        "z_score": round(z, 4),
    }


async def get_llm_cost_metrics(tenant_id: str, db: Any) -> LLMCostMetrics:
    """Get LLM usage and cost metrics from agent_decisions. Risk: LOW."""
    config = AILabConfig()
    rows = db.fetch_all(
        """SELECT llm_model_used, COUNT(*) as calls
           FROM shared_analytics.agent_decisions
           WHERE tenant_id = ?
           GROUP BY llm_model_used""",
        [tenant_id],
    )

    breakdown = {}
    total_cost = 0.0
    for row in rows:
        model = row.get("llm_model_used", "unknown")
        calls = row.get("calls", 0)
        # Approximate cost per call
        if "opus" in model:
            cost = calls * 0.075
        elif "sonnet" in model:
            cost = calls * 0.015
        else:
            cost = calls * 0.001
        breakdown[model] = {"calls": calls, "cost_usd": round(cost, 4)}
        total_cost += cost

    budget_pct = (total_cost / (config.token_budget_monthly * 0.00001)) * 100 if config.token_budget_monthly else 0

    if budget_pct > config.token_budget_warn_pct:
        logger.warning("token_budget_warning", tenant_id=tenant_id, budget_pct=round(budget_pct, 1))

    return LLMCostMetrics(
        tenant_id=tenant_id,
        total_cost_usd=round(total_cost, 4),
        budget_used_pct=round(budget_pct, 2),
        model_breakdown=breakdown,
    )


async def evaluate_model(
    tenant_id: str, model_name: str, metrics: dict[str, Any],
) -> ModelEvaluation:
    """Evaluate model performance. Risk: LOW."""
    drift = metrics.get("accuracy", 1.0) < 0.85
    return ModelEvaluation(
        model_name=model_name,
        tenant_id=tenant_id,
        accuracy=metrics.get("accuracy", 0.0),
        latency_p50_ms=metrics.get("latency_p50_ms", 0),
        latency_p99_ms=metrics.get("latency_p99_ms", 0),
        cost_per_request=metrics.get("cost_per_request", 0.0),
        drift_detected=drift,
    )


# ── MEDIUM risk tools ───────────────────────────────────


async def register_prompt_version(
    tenant_id: str, app: str, prompt_type: str, content: str, version: int,
) -> PromptVersion:
    """Register a new prompt version. Risk: MEDIUM (auto+notify)."""
    pv = PromptVersion(app=app, prompt_type=prompt_type, version=version, content=content)
    logger.info(
        "prompt_version_registered",
        tenant_id=tenant_id, app=app, prompt_type=prompt_type, version=version,
    )
    return pv


# ── HIGH risk tools ─────────────────────────────────────


async def update_model_config(
    tenant_id: str, model_name: str, config_updates: dict[str, Any],
) -> dict:
    """Update model configuration. Risk: HIGH (approval_required)."""
    logger.warning(
        "model_config_update_requested",
        tenant_id=tenant_id, model=model_name, updates=config_updates,
    )
    return {
        "status": "approval_required",
        "model_name": model_name,
        "config_updates": config_updates,
    }


async def switch_model_production(
    tenant_id: str, model_name: str, target_version: str,
) -> dict:
    """Switch production model version. Risk: HIGH (approval_required)."""
    logger.warning(
        "model_production_switch_requested",
        tenant_id=tenant_id, model=model_name, target=target_version,
    )
    return {
        "status": "approval_required",
        "model_name": model_name,
        "target_version": target_version,
    }
