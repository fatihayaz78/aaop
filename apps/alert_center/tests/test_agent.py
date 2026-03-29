"""Tests for AlertRouterAgent."""

from __future__ import annotations

import pytest

from apps.alert_center.agent import SUBSCRIBED_EVENTS, AlertRouterAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


def test_subscribes_to_all_7_events():
    assert len(SUBSCRIBED_EVENTS) == 7
    assert "cdn_anomaly_detected" in SUBSCRIBED_EVENTS
    assert "incident_created" in SUBSCRIBED_EVENTS
    assert "rca_completed" in SUBSCRIBED_EVENTS
    assert "qoe_degradation" in SUBSCRIBED_EVENTS
    assert "live_event_starting" in SUBSCRIBED_EVENTS
    assert "churn_risk_detected" in SUBSCRIBED_EVENTS
    assert "scale_recommendation" in SUBSCRIBED_EVENTS


@pytest.mark.asyncio
async def test_route_p0_slack_pagerduty(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {
        "event_type": "cdn_anomaly_detected",
        "severity": "P0",
        "source_app": "log_analyzer",
        "title": "Total CDN outage",
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result.get("error") is None
    output = result["output"]
    assert output["action"] == "route"
    assert "slack" in output["channels"]
    assert "pagerduty" in output["channels"]
    assert output["approval_required"] is True


@pytest.mark.asyncio
async def test_route_p1_slack_only(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"severity": "P1", "title": "CDN Error Spike", "source_app": "ops_center"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["channels"] == ["slack"]
    assert result["output"]["approval_required"] is False


@pytest.mark.asyncio
async def test_route_p2_slack(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"severity": "P2", "title": "QoE dip", "source_app": "viewer_experience"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["channels"] == ["slack"]


@pytest.mark.asyncio
async def test_route_p3_email(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"severity": "P3", "title": "Log warning", "source_app": "log_analyzer"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["channels"] == ["email"]


@pytest.mark.asyncio
async def test_dedup_drops_alert(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"severity": "P1", "title": "Dup", "dedup_hit": True}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "dedup_drop"


@pytest.mark.asyncio
async def test_storm_detection(mock_llm: LLMGateway, event_bus: EventBus):
    """Sending >10 alerts triggers storm mode."""
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="storm_test")
    await event_bus.start()

    # Fire 11 alerts to trigger storm
    for i in range(11):
        input_data = {"severity": "P2", "title": f"Alert {i}", "source_app": "test"}
        result = await agent.run(ctx, input_data=input_data)

    await event_bus.stop()

    # The 11th (or later) should trigger storm
    assert result["output"]["action"] == "storm_summary"
    assert result["output"]["approval_required"] is True


@pytest.mark.asyncio
async def test_model_routing_p0_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    """P0 should use Sonnet for message generation."""
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    assert agent.get_llm_model("P0") == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_model_routing_p3_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    """P3 should use Haiku for routing."""
    agent = AlertRouterAgent(llm_gateway=mock_llm, event_bus=event_bus)
    assert agent.get_llm_model("P3") == "claude-haiku-4-5-20251001"
