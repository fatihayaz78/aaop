"""Tests for Alert Center tools — dedup, storm, routing, risk levels."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.alert_center.schemas import Alert
from apps.alert_center.tools import (
    check_dedup,
    detect_alert_storm,
    get_routing_rules,
    route_to_email,
    route_to_pagerduty,
    route_to_slack,
    set_dedup_cache,
    suppress_alert_storm,
)
from shared.schemas.base_event import SeverityLevel


@pytest.mark.asyncio
async def test_check_dedup_no_hit(mock_redis: MagicMock):
    mock_redis.exists = AsyncMock(return_value=False)
    result = await check_dedup("t1", "log_analyzer", "cdn_anomaly", "P1", mock_redis)
    assert result is False


@pytest.mark.asyncio
async def test_check_dedup_hit(mock_redis: MagicMock):
    mock_redis.exists = AsyncMock(return_value=True)
    result = await check_dedup("t1", "log_analyzer", "cdn_anomaly", "P1", mock_redis)
    assert result is True


@pytest.mark.asyncio
async def test_set_dedup_cache_ttl(mock_redis: MagicMock):
    await set_dedup_cache("t1", "log_analyzer", "cdn_anomaly", "P1", mock_redis)
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args.kwargs.get("ttl") == 900  # 900s dedup window


@pytest.mark.asyncio
async def test_routing_p0():
    result = await get_routing_rules("t1", "cdn_anomaly", "P0")
    assert "slack" in result["channels"]
    assert "pagerduty" in result["channels"]
    assert result["approval_required"] is True


@pytest.mark.asyncio
async def test_routing_p1():
    result = await get_routing_rules("t1", "incident", "P1")
    assert result["channels"] == ["slack"]


@pytest.mark.asyncio
async def test_routing_p2():
    result = await get_routing_rules("t1", "qoe", "P2")
    assert result["channels"] == ["slack"]


@pytest.mark.asyncio
async def test_routing_p3():
    result = await get_routing_rules("t1", "info", "P3")
    assert result["channels"] == ["email"]


@pytest.mark.asyncio
async def test_storm_detection_under_threshold():
    for _ in range(5):
        result = await detect_alert_storm("t_under")
    assert result is False


@pytest.mark.asyncio
async def test_storm_detection_over_threshold():
    for _ in range(11):
        result = await detect_alert_storm("t_over")
    assert result is True


@pytest.mark.asyncio
async def test_route_to_slack():
    alert = Alert(tenant_id="t1", source_app="ops", event_type="incident", severity=SeverityLevel.P1, title="Test")
    result = await route_to_slack("t1", alert)
    assert result["status"] == "sent"
    assert result["channel"] == "slack"


@pytest.mark.asyncio
async def test_route_to_email():
    alert = Alert(tenant_id="t1", source_app="ops", event_type="info", severity=SeverityLevel.P3, title="Info")
    result = await route_to_email("t1", alert)
    assert result["status"] == "sent"
    assert result["channel"] == "email"


@pytest.mark.asyncio
async def test_route_to_pagerduty_approval():
    alert = Alert(tenant_id="t1", source_app="ops", event_type="incident", severity=SeverityLevel.P0, title="Outage")
    result = await route_to_pagerduty("t1", alert)
    assert result["status"] == "approval_required"
    assert result["channel"] == "pagerduty"


@pytest.mark.asyncio
async def test_suppress_alert_storm_approval():
    result = await suppress_alert_storm("t1", "15 alerts in 5 minutes")
    assert result["status"] == "approval_required"
    assert result["action"] == "suppress_storm"
