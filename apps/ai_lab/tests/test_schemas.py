"""Tests for AI Lab schemas."""

from __future__ import annotations

from apps.ai_lab.schemas import (
    Experiment,
    ExperimentResult,
    LLMCostMetrics,
    ModelEvaluation,
    ModelRegistryEntry,
    PromptVersion,
)


def test_experiment_defaults():
    e = Experiment(tenant_id="t1", name="Test A/B")
    assert e.experiment_id.startswith("EXP-")
    assert e.status == "draft"
    assert e.variants == []


def test_experiment_result():
    r = ExperimentResult(experiment_id="e1", variant_id="v1", sample_size=100, p_value=0.03, is_significant=True)
    assert r.is_significant is True


def test_model_registry():
    m = ModelRegistryEntry(model_name="claude-sonnet")
    assert m.model_id.startswith("MDL-")
    assert m.is_active is True


def test_prompt_version():
    p = PromptVersion(app="ops_center", prompt_type="system", content="You are...")
    assert p.prompt_id.startswith("PRM-")
    assert p.version == 1


def test_llm_cost_metrics():
    m = LLMCostMetrics(tenant_id="t1", total_cost_usd=150.0, budget_used_pct=75.0)
    assert m.budget_used_pct == 75.0


def test_model_evaluation():
    e = ModelEvaluation(model_name="sonnet", tenant_id="t1", accuracy=0.92)
    assert e.eval_id.startswith("EVAL-")
    assert e.drift_detected is False
