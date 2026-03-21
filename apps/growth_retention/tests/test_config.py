"""Tests for Growth & Retention config."""

from __future__ import annotations

from apps.growth_retention.config import GrowthRetentionConfig


def test_defaults():
    cfg = GrowthRetentionConfig()
    assert cfg.churn_risk_threshold == 0.7
    assert cfg.retention_analysis_interval_hours == 24
    assert cfg.max_sql_results == 1000
    assert "qoe_metrics" in cfg.allowed_tables
    assert "shared_analytics" in cfg.allowed_schemas


def test_custom():
    cfg = GrowthRetentionConfig(churn_risk_threshold=0.8, max_sql_results=500)
    assert cfg.churn_risk_threshold == 0.8
    assert cfg.max_sql_results == 500
