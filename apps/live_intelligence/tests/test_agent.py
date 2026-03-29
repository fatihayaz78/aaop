"""Tests for LiveEventAgent and ExternalDataAgent."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from apps.live_intelligence.agent import ExternalDataAgent, LiveEventAgent, should_trigger_start
from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── should_trigger_start tests ──


def test_trigger_start_within_window():
    kickoff = datetime.now(UTC) + timedelta(minutes=15)
    assert should_trigger_start(kickoff, trigger_minutes=30) is True


def test_trigger_start_too_early():
    kickoff = datetime.now(UTC) + timedelta(hours=2)
    assert should_trigger_start(kickoff, trigger_minutes=30) is False


def test_trigger_start_past():
    kickoff = datetime.now(UTC) - timedelta(minutes=10)
    assert should_trigger_start(kickoff, trigger_minutes=30) is False


def test_trigger_start_none():
    assert should_trigger_start(None) is False


# ── LiveEventAgent tests ──


@pytest.mark.asyncio
async def test_live_event_agent_no_event(mock_llm: LLMGateway, event_bus: EventBus):
    agent = LiveEventAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_event"


@pytest.mark.asyncio
async def test_live_event_agent_triggers_start(mock_llm: LLMGateway, event_bus: EventBus):
    """Event starting within 30 min should trigger live_event_starting."""
    agent = LiveEventAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    kickoff = datetime.now(UTC) + timedelta(minutes=20)
    input_data = {
        "event": {
            "event_name": "GS vs FB",
            "sport": "football",
            "competition": "Super Lig",
            "kickoff_time": kickoff.isoformat(),
            "expected_viewers": 500_000,
        },
    }

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.LIVE_EVENT_STARTING, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert result.get("error") is None
    assert result["output"]["action"] == "trigger_event_start"
    assert result["output"]["event_start_published"] is True
    assert len(received) == 1


@pytest.mark.asyncio
async def test_live_event_agent_monitor_only(mock_llm: LLMGateway, event_bus: EventBus):
    """Event far away should just monitor, not trigger start."""
    agent = LiveEventAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    kickoff = datetime.now(UTC) + timedelta(hours=5)
    input_data = {
        "event": {
            "event_name": "Match",
            "kickoff_time": kickoff.isoformat(),
            "expected_viewers": 50_000,
        },
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "monitor_event"
    assert result["output"]["event_start_published"] is False


@pytest.mark.asyncio
async def test_live_event_scale_factor(mock_llm: LLMGateway, event_bus: EventBus):
    agent = LiveEventAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    kickoff = datetime.now(UTC) + timedelta(hours=3)
    input_data = {
        "event": {"event_name": "Derby", "kickoff_time": kickoff.isoformat(), "expected_viewers": 600_000},
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["scale_factor"] == 3.0


# ── ExternalDataAgent tests ──


@pytest.mark.asyncio
async def test_external_agent_with_change(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExternalDataAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "connector": "sportradar",
        "data": {"score": "1-0", "minute": 45},
        "previous_data": {"score": "0-0", "minute": 30},
    }

    received: list[Any] = []

    async def handler(e: Any) -> None:
        received.append(e)

    event_bus.subscribe(EventType.EXTERNAL_DATA_UPDATED, handler)
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert result["output"]["update_published"] is True
    assert len(received) == 1


@pytest.mark.asyncio
async def test_external_agent_no_change(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExternalDataAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    same_data = {"score": "0-0"}
    input_data = {"connector": "epg", "data": same_data, "previous_data": same_data}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["update_published"] is False


@pytest.mark.asyncio
async def test_external_agent_no_connector(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExternalDataAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_connector"


@pytest.mark.asyncio
async def test_external_agent_uses_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    """ExternalDataAgent should use Haiku (P3 severity)."""
    agent = ExternalDataAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"connector": "drm", "data": {"widevine": "healthy"}, "previous_data": {}}
    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "haiku" in model_used
