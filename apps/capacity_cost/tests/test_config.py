"""Tests for Capacity & Cost config."""

from __future__ import annotations

from apps.capacity_cost.config import CapacityCostConfig


def test_defaults():
    cfg = CapacityCostConfig()
    assert cfg.warn_threshold_pct == 70.0
    assert cfg.crit_threshold_pct == 90.0
    assert cfg.forecast_horizon_hours == 24
    assert cfg.usage_check_interval_minutes == 60
    assert cfg.pre_scale_lead_minutes == 30
    assert cfg.cost_currency == "USD"
    assert cfg.max_scale_factor == 5.0


def test_custom():
    cfg = CapacityCostConfig(warn_threshold_pct=60.0, crit_threshold_pct=85.0)
    assert cfg.warn_threshold_pct == 60.0
    assert cfg.crit_threshold_pct == 85.0
