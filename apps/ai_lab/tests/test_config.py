"""Tests for AI Lab config."""

from __future__ import annotations

from apps.ai_lab.config import AILabConfig


def test_defaults():
    cfg = AILabConfig()
    assert cfg.token_budget_warn_pct == 80.0
    assert cfg.token_budget_monthly == 10_000_000
    assert cfg.experiment_max_variants == 5
    assert cfg.significance_threshold == 0.05
    assert cfg.prompt_version_retention == 10


def test_custom():
    cfg = AILabConfig(token_budget_warn_pct=90.0, experiment_max_variants=3)
    assert cfg.token_budget_warn_pct == 90.0
    assert cfg.experiment_max_variants == 3
