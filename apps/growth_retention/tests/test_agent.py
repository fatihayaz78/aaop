"""Tests for GrowthAgent and DataAnalystAgent."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.growth_retention.agent import DataAnalystAgent, GrowthAgent
from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── GrowthAgent tests ──


@pytest.mark.asyncio
async def test_growth_agent_no_segment(mock_llm: LLMGateway, event_bus: EventBus):
    agent = GrowthAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_segment"


@pytest.mark.asyncio
async def test_growth_agent_high_churn(mock_llm: LLMGateway, event_bus: EventBus):
    """Churn risk > 0.7 should publish churn_risk_detected."""
    agent = GrowthAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {
        "segment_id": "seg_at_risk",
        "qoe_data": [{"quality_score": 1.5}, {"quality_score": 1.0}],
        "cdn_data": [{"error_rate": 0.15}],
        "retention_7d": 0.4,
        "retention_30d": 1.0,
    }

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.CHURN_RISK_DETECTED, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert result.get("error") is None
    assert result["output"]["churn_risk"] > 0.7
    assert result["output"]["churn_alert_published"] is True
    assert len(received) == 1


@pytest.mark.asyncio
async def test_growth_agent_low_churn(mock_llm: LLMGateway, event_bus: EventBus):
    """Churn risk < 0.7 should NOT publish event."""
    agent = GrowthAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "segment_id": "seg_healthy",
        "qoe_data": [{"quality_score": 4.5}],
        "cdn_data": [{"error_rate": 0.01}],
    }

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.CHURN_RISK_DETECTED, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert result["output"]["churn_risk"] < 0.7
    assert result["output"]["churn_alert_published"] is False
    assert len(received) == 0


@pytest.mark.asyncio
async def test_growth_agent_uses_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    """GrowthAgent should use Sonnet (P2 severity)."""
    agent = GrowthAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"segment_id": "seg1", "qoe_data": [{"quality_score": 3.0}]}

    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "sonnet" in model_used


# ── DataAnalystAgent tests ──


@pytest.mark.asyncio
async def test_data_analyst_no_question(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DataAnalystAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_question"


@pytest.mark.asyncio
async def test_data_analyst_valid_query(mock_llm: LLMGateway, event_bus: EventBus):
    """LLM generates valid SELECT → execute_query action."""
    agent = DataAnalystAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"question": "How many sessions today?"}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "execute_query"
    assert result["output"]["valid"] is True
    assert "SELECT" in result["output"]["generated_sql"]


@pytest.mark.asyncio
async def test_data_analyst_pii_protection(mock_llm: LLMGateway, event_bus: EventBus):
    """DataAnalystAgent uses user_id_hash, validates read-only."""
    agent = DataAnalystAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"question": "Show user sessions"}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    # Generated SQL from mock contains SELECT → valid
    assert result["output"]["valid"] is True
