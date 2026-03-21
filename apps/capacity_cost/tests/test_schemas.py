"""Tests for Capacity & Cost schemas."""

from __future__ import annotations

from apps.capacity_cost.schemas import (
    AutomationJob,
    CapacityForecast,
    CapacityMetrics,
    CostReport,
    ScaleAction,
    ThresholdBreach,
)


def test_capacity_metrics_usage_pct():
    m = CapacityMetrics(tenant_id="t1", metric="bandwidth", current_value=75, max_value=100)
    assert m.usage_pct == 75.0


def test_capacity_metrics_zero_max():
    m = CapacityMetrics(tenant_id="t1", metric="cpu", current_value=50, max_value=0)
    assert m.usage_pct == 0.0


def test_capacity_forecast_defaults():
    f = CapacityForecast(tenant_id="t1", metric="bandwidth", current_pct=65.0, predicted_pct=72.0)
    assert f.forecast_id.startswith("FCT-")
    assert f.trend == "stable"
    assert f.breach_estimated_hours is None


def test_threshold_breach():
    b = ThresholdBreach(tenant_id="t1", metric="cpu", current_pct=92.0, threshold_pct=90.0, level="critical")
    assert b.level == "critical"


def test_cost_report():
    r = CostReport(tenant_id="t1", period="daily", total_cost=1500.0, breakdown={"cdn": 1000.0, "compute": 500.0})
    assert r.report_id.startswith("COST-")
    assert r.currency == "USD"


def test_scale_action():
    a = ScaleAction(tenant_id="t1", resource="cdn", action_type="scale_up", scale_factor=2.0)
    assert a.action_id.startswith("SCALE-")
    assert a.status == "pending"


def test_automation_job():
    j = AutomationJob(tenant_id="t1", job_type="scale")
    assert j.job_id.startswith("JOB-")
    assert j.status == "pending"
    assert j.started_at is None
