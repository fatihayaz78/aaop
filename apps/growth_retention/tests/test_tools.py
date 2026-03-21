"""Tests for Growth & Retention tools."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from apps.growth_retention.config import GrowthRetentionConfig
from apps.growth_retention.schemas import RetentionCampaign, RetentionScore
from apps.growth_retention.tools import (
    calculate_churn_risk,
    get_cdn_impact,
    get_growth_insights,
    get_qoe_correlation,
    nl_to_sql_query,
    segment_customers,
    send_retention_campaign,
    trigger_churn_alert,
    validate_sql_query,
    write_analysis_result,
)
from shared.event_bus import EventBus, EventType

# ── Churn risk calculation ──


@pytest.mark.asyncio
async def test_churn_high_risk():
    result = await calculate_churn_risk("t1", "seg1", qoe_avg=1.0, cdn_error_rate=0.15, retention_7d=0.3, retention_30d=1.0)
    assert result.churn_risk > 0.7
    assert "low_qoe" in result.factors
    assert "high_cdn_errors" in result.factors


@pytest.mark.asyncio
async def test_churn_low_risk():
    result = await calculate_churn_risk("t1", "seg1", qoe_avg=4.5, cdn_error_rate=0.01)
    assert result.churn_risk < 0.3
    assert result.recommendation == "Low risk — continue monitoring"


@pytest.mark.asyncio
async def test_churn_moderate_risk():
    result = await calculate_churn_risk("t1", "seg1", qoe_avg=2.0, cdn_error_rate=0.03)
    assert 0.1 < result.churn_risk < 0.8


@pytest.mark.asyncio
async def test_churn_with_declining_retention():
    result = await calculate_churn_risk("t1", "seg1", qoe_avg=3.0, cdn_error_rate=0.02, retention_7d=0.3, retention_30d=1.0)
    assert "declining_retention" in result.factors


@pytest.mark.asyncio
async def test_churn_risk_capped_at_1():
    result = await calculate_churn_risk("t1", "seg1", qoe_avg=0.5, cdn_error_rate=0.5, retention_7d=0.1, retention_30d=1.0)
    assert result.churn_risk <= 1.0


# ── SQL validation ──


def test_validate_select_valid():
    config = GrowthRetentionConfig()
    ok, msg = validate_sql_query("SELECT * FROM shared_analytics.qoe_metrics WHERE tenant_id='t1'", config)
    assert ok is True


def test_validate_insert_blocked():
    config = GrowthRetentionConfig()
    ok, msg = validate_sql_query("INSERT INTO shared_analytics.qoe_metrics VALUES ('x')", config)
    assert ok is False
    assert "SELECT" in msg or "INSERT" in msg


def test_validate_delete_blocked():
    config = GrowthRetentionConfig()
    ok, msg = validate_sql_query("DELETE FROM shared_analytics.qoe_metrics", config)
    assert ok is False


def test_validate_drop_blocked():
    config = GrowthRetentionConfig()
    ok, msg = validate_sql_query("DROP TABLE shared_analytics.qoe_metrics", config)
    assert ok is False


def test_validate_no_allowed_table():
    config = GrowthRetentionConfig()
    ok, msg = validate_sql_query("SELECT * FROM some_other_table", config)
    assert ok is False
    assert "shared_analytics" in msg


# ── NL to SQL query ──


@pytest.mark.asyncio
async def test_nl_to_sql_valid(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"count": 42}])
    result = await nl_to_sql_query(
        "t1", "How many sessions?",
        "SELECT COUNT(*) as count FROM shared_analytics.qoe_metrics WHERE tenant_id='t1'",
        mock_db,
    )
    assert result.row_count == 1
    assert result.execution_time_ms >= 0


@pytest.mark.asyncio
async def test_nl_to_sql_invalid():
    mock_db = MagicMock()
    result = await nl_to_sql_query("t1", "delete all", "DELETE FROM shared_analytics.qoe_metrics", mock_db)
    assert result.row_count == 0


# ── DuckDB read tools ──


@pytest.mark.asyncio
async def test_get_qoe_correlation(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"user_id_hash": "abc", "avg_qoe": 3.5}])
    result = await get_qoe_correlation("t1", mock_db)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_cdn_impact(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"sub_module": "akamai", "avg_error_rate": 0.02}])
    result = await get_cdn_impact("t1", mock_db)
    assert len(result) == 1


# ── Segment tool ──


@pytest.mark.asyncio
async def test_segment_customers():
    seg = await segment_customers("t1", {"name": "at_risk", "size": 100, "avg_churn_risk": 0.8})
    assert seg.name == "at_risk"
    assert seg.size == 100


# ── Growth insights ──


@pytest.mark.asyncio
async def test_growth_insights_high_churn():
    insights = await get_growth_insights("t1", {"churn_risk": 0.85})
    assert len(insights) == 1
    assert insights[0].category == "retention"


@pytest.mark.asyncio
async def test_growth_insights_low_qoe():
    insights = await get_growth_insights("t1", {"avg_qoe": 2.0})
    assert len(insights) == 1
    assert insights[0].category == "engagement"


@pytest.mark.asyncio
async def test_growth_insights_none():
    insights = await get_growth_insights("t1", {"churn_risk": 0.3, "avg_qoe": 4.5})
    assert len(insights) == 0


# ── MEDIUM risk: write + alert ──


@pytest.mark.asyncio
async def test_write_analysis_result(mock_db: MagicMock):
    score = RetentionScore(tenant_id="t1", segment_id="seg1", churn_risk=0.8)
    result = await write_analysis_result("t1", score, mock_db)
    assert result == score.score_id
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_churn_alert(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.CHURN_RISK_DETECTED, handler)
    await event_bus.start()
    await trigger_churn_alert("t1", "seg1", 0.85, event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].payload["churn_risk"] == 0.85


# ── HIGH risk: campaign ──


@pytest.mark.asyncio
async def test_send_retention_campaign_approval():
    campaign = RetentionCampaign(tenant_id="t1", segment_id="seg1", campaign_type="email")
    result = await send_retention_campaign("t1", campaign)
    assert result["status"] == "approval_required"
    assert result["campaign_type"] == "email"
