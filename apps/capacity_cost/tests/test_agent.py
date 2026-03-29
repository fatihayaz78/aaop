"""Tests for CapacityAgent and AutomationAgent."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.capacity_cost.agent import AutomationAgent, CapacityAgent
from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── CapacityAgent tests ──


@pytest.mark.asyncio
async def test_capacity_agent_monitor(mock_llm: LLMGateway, event_bus: EventBus):
    """Normal capacity should just monitor."""
    agent = CapacityAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"metric": "bandwidth", "current_pct": 50.0, "trend": "stable"}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result.get("error") is None
    assert result["output"]["action"] == "monitor"
    assert result["output"]["scale_published"] is False


@pytest.mark.asyncio
async def test_capacity_agent_critical_breach(mock_llm: LLMGateway, event_bus: EventBus):
    """Critical threshold should publish scale_recommendation."""
    agent = CapacityAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {"metric": "bandwidth", "current_pct": 95.0, "trend": "growing"}

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.SCALE_RECOMMENDATION, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert result["output"]["action"] == "scale_critical"
    assert result["output"]["scale_published"] is True
    assert len(received) == 1


@pytest.mark.asyncio
async def test_capacity_agent_warn_breach(mock_llm: LLMGateway, event_bus: EventBus):
    """Warn threshold should also publish scale_recommendation."""
    agent = CapacityAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"metric": "cpu", "current_pct": 75.0, "trend": "growing"}

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.SCALE_RECOMMENDATION, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert result["output"]["action"] == "scale_warn"
    assert result["output"]["scale_published"] is True
    assert len(received) == 1


@pytest.mark.asyncio
async def test_capacity_agent_pre_scale(mock_llm: LLMGateway, event_bus: EventBus):
    """Live event with >50k viewers should trigger pre_scale."""
    agent = CapacityAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "metric": "bandwidth",
        "current_pct": 40.0,
        "live_event": {"event_name": "Derby", "expected_viewers": 500_000},
    }

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "pre_scale"
    assert result["output"]["needs_pre_scale"] is True


@pytest.mark.asyncio
async def test_capacity_agent_uses_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    """CapacityAgent should use Sonnet (P2 severity)."""
    agent = CapacityAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"metric": "bandwidth", "current_pct": 60.0}

    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "sonnet" in model_used


# ── AutomationAgent tests ──


@pytest.mark.asyncio
async def test_automation_agent_no_job(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AutomationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_job"


@pytest.mark.asyncio
async def test_automation_agent_create_job(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AutomationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"job_type": "cleanup", "job_config": {"target": "logs"}}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "create_job"
    assert result["output"]["job_type"] == "cleanup"


@pytest.mark.asyncio
async def test_automation_agent_scale_action(mock_llm: LLMGateway, event_bus: EventBus):
    agent = AutomationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"job_type": "scale", "resource": "cdn", "scale_factor": 2.5}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "scale_action"
    assert result["output"]["scale_factor"] == 2.5


@pytest.mark.asyncio
async def test_automation_agent_uses_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    """AutomationAgent should use Haiku (P3 severity)."""
    agent = AutomationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"job_type": "optimize"}

    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "haiku" in model_used
