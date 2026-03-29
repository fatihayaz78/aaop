"""Tests for DevOpsAssistantAgent."""

from __future__ import annotations

import pytest

from apps.devops_assistant.agent import DevOpsAssistantAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


@pytest.mark.asyncio
async def test_diagnose(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "diagnose", "service": "fastapi"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "diagnose"
    assert result["output"]["service"] == "fastapi"


@pytest.mark.asyncio
async def test_no_service(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "diagnose"})
    await event_bus.stop()
    assert result["output"]["action"] == "no_service"


@pytest.mark.asyncio
async def test_restart_service(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "restart", "service": "nginx"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "restart_service"


@pytest.mark.asyncio
async def test_execute_runbook(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "runbook", "runbook_id": "rb-1"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "execute_runbook"


@pytest.mark.asyncio
async def test_suggest_command(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "suggest", "intent": "check pods"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "suggest_command"


@pytest.mark.asyncio
async def test_search_runbooks(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "search_runbooks", "query": "restart cdn"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "search_runbooks"


@pytest.mark.asyncio
async def test_uses_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    agent = DevOpsAssistantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "diagnose", "service": "backend"}
    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "sonnet" in call_kwargs.kwargs.get("model", "")
