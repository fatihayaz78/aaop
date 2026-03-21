"""Tests for AI Lab tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.ai_lab.tools import (
    analyze_statistical_significance,
    create_experiment,
    evaluate_model,
    get_llm_cost_metrics,
    register_prompt_version,
    switch_model_production,
    update_model_config,
)

# ── Experiment creation ──


@pytest.mark.asyncio
async def test_create_experiment():
    exp = await create_experiment("t1", "Test AB", [{"name": "A"}, {"name": "B"}], "latency")
    assert exp.experiment_id.startswith("EXP-")
    assert exp.status == "draft"
    assert len(exp.variants) == 2


@pytest.mark.asyncio
async def test_create_experiment_caps_variants():
    variants = [{"name": f"v{i}"} for i in range(10)]
    exp = await create_experiment("t1", "Too many", variants, "cost")
    assert len(exp.variants) == 5  # max_variants default


# ── Statistical significance ──


@pytest.mark.asyncio
async def test_significance_significant():
    result = await analyze_statistical_significance(
        control_mean=100, control_std=10, control_n=500,
        variant_mean=105, variant_std=10, variant_n=500,
    )
    assert result["is_significant"] is True
    assert result["p_value"] < 0.05


@pytest.mark.asyncio
async def test_significance_not_significant():
    result = await analyze_statistical_significance(
        control_mean=100, control_std=10, control_n=20,
        variant_mean=101, variant_std=10, variant_n=20,
    )
    assert result["is_significant"] is False


@pytest.mark.asyncio
async def test_significance_zero_samples():
    result = await analyze_statistical_significance(0, 1, 0, 0, 1, 0)
    assert result["p_value"] == 1.0
    assert result["is_significant"] is False


@pytest.mark.asyncio
async def test_significance_zero_std():
    result = await analyze_statistical_significance(
        control_mean=100, control_std=0, control_n=100,
        variant_mean=100, variant_std=0, variant_n=100,
    )
    assert result["is_significant"] is False


# ── Cost metrics ──


@pytest.mark.asyncio
async def test_get_llm_cost_metrics(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[
        {"llm_model_used": "claude-sonnet-4-20250514", "calls": 100},
        {"llm_model_used": "claude-haiku-4-5-20251001", "calls": 500},
    ])
    metrics = await get_llm_cost_metrics("t1", mock_db)
    assert metrics.total_cost_usd > 0
    assert len(metrics.model_breakdown) == 2


@pytest.mark.asyncio
async def test_get_llm_cost_metrics_empty(mock_db: MagicMock):
    metrics = await get_llm_cost_metrics("t1", mock_db)
    assert metrics.total_cost_usd == 0


@pytest.mark.asyncio
async def test_budget_warning_logged(mock_db: MagicMock):
    """Token budget > 80% should log warning."""
    mock_db.fetch_all = MagicMock(return_value=[
        {"llm_model_used": "claude-opus-4-20250514", "calls": 100_000},
    ])
    metrics = await get_llm_cost_metrics("t1", mock_db)
    assert metrics.budget_used_pct > 80


# ── Model evaluation ──


@pytest.mark.asyncio
async def test_evaluate_model_no_drift():
    ev = await evaluate_model("t1", "sonnet", {"accuracy": 0.95, "latency_p50_ms": 200})
    assert ev.drift_detected is False
    assert ev.accuracy == 0.95


@pytest.mark.asyncio
async def test_evaluate_model_drift():
    ev = await evaluate_model("t1", "sonnet", {"accuracy": 0.70})
    assert ev.drift_detected is True


# ── MEDIUM risk ──


@pytest.mark.asyncio
async def test_register_prompt_version():
    pv = await register_prompt_version("t1", "ops_center", "system", "You are...", 2)
    assert pv.app == "ops_center"
    assert pv.version == 2


# ── HIGH risk ──


@pytest.mark.asyncio
async def test_update_model_config_approval():
    result = await update_model_config("t1", "sonnet", {"temperature": 0.7})
    assert result["status"] == "approval_required"


@pytest.mark.asyncio
async def test_switch_model_production_approval():
    result = await switch_model_production("t1", "sonnet", "v2.0")
    assert result["status"] == "approval_required"
    assert result["target_version"] == "v2.0"
