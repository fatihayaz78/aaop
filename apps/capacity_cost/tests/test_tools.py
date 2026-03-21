"""Tests for Capacity & Cost tools."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from apps.capacity_cost.schemas import AutomationJob, CapacityForecast, ScaleAction
from apps.capacity_cost.tools import (
    calculate_cost,
    create_automation_job,
    detect_threshold_breach,
    execute_scale_action,
    forecast_capacity,
    get_current_metrics,
    publish_scale_recommendation,
    write_forecast,
)
from shared.event_bus import EventBus, EventType

# ── Forecast tests ──


@pytest.mark.asyncio
async def test_forecast_stable():
    fc = await forecast_capacity("t1", "bandwidth", current_pct=50.0, trend="stable")
    assert fc.predicted_pct == 50.0
    assert fc.confidence == 0.85
    assert fc.breach_estimated_hours is None


@pytest.mark.asyncio
async def test_forecast_growing():
    fc = await forecast_capacity("t1", "cpu", current_pct=70.0, trend="growing", horizon_hours=24)
    assert fc.predicted_pct > 70.0
    assert fc.confidence == 0.65


@pytest.mark.asyncio
async def test_forecast_growing_breach():
    fc = await forecast_capacity("t1", "bandwidth", current_pct=80.0, trend="growing", horizon_hours=48)
    assert fc.breach_estimated_hours is not None
    assert fc.breach_estimated_hours > 0


@pytest.mark.asyncio
async def test_forecast_declining():
    fc = await forecast_capacity("t1", "memory", current_pct=60.0, trend="declining")
    assert fc.predicted_pct < 60.0


# ── Threshold breach ──


@pytest.mark.asyncio
async def test_breach_critical():
    breach = await detect_threshold_breach("t1", "bandwidth", 95.0)
    assert breach is not None
    assert breach.level == "critical"
    assert "CRITICAL" in breach.message


@pytest.mark.asyncio
async def test_breach_warn():
    breach = await detect_threshold_breach("t1", "cpu", 75.0)
    assert breach is not None
    assert breach.level == "warn"


@pytest.mark.asyncio
async def test_no_breach():
    breach = await detect_threshold_breach("t1", "memory", 50.0)
    assert breach is None


# ── Cost calculation ──


@pytest.mark.asyncio
async def test_calculate_cost():
    report = await calculate_cost("t1", period="daily", breakdown={"cdn": 1000.0, "compute": 500.0}, total_viewers=100_000)
    assert report.total_cost == 1500.0
    assert report.cost_per_viewer == 0.015


@pytest.mark.asyncio
async def test_calculate_cost_no_viewers():
    report = await calculate_cost("t1", breakdown={"cdn": 100.0})
    assert report.cost_per_viewer == 0.0


# ── DuckDB read ──


@pytest.mark.asyncio
async def test_get_current_metrics(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"event_name": "Derby", "peak_viewers": 500000}])
    result = await get_current_metrics("t1", mock_db)
    assert len(result) == 1


# ── MEDIUM risk: write + publish ──


@pytest.mark.asyncio
async def test_write_forecast(mock_db: MagicMock):
    fc = CapacityForecast(tenant_id="t1", metric="bandwidth", current_pct=70.0, predicted_pct=85.0, confidence=0.8)
    decision_id = await write_forecast("t1", fc, mock_db)
    assert decision_id.startswith("DEC-")
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_publish_scale_recommendation(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.SCALE_RECOMMENDATION, handler)
    await event_bus.start()
    await publish_scale_recommendation("t1", "bandwidth", 92.0, 2.0, "Critical threshold", event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].payload["scale_factor"] == 2.0


# ── HIGH risk tools ──


@pytest.mark.asyncio
async def test_create_automation_job_approval():
    job = AutomationJob(tenant_id="t1", job_type="scale", config={"target": "cdn"})
    result = await create_automation_job("t1", job)
    assert result["status"] == "approval_required"
    assert result["job_type"] == "scale"


@pytest.mark.asyncio
async def test_execute_scale_action_approval():
    action = ScaleAction(tenant_id="t1", resource="cdn", action_type="scale_up", scale_factor=3.0, reason="Live event")
    result = await execute_scale_action("t1", action)
    assert result["status"] == "approval_required"
    assert result["resource"] == "cdn"
    assert result["scale_factor"] == 3.0
