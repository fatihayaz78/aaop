"""Tests for ExperimentationAgent and ModelGovernanceAgent."""

from __future__ import annotations

import pytest

from apps.ai_lab.agent import ExperimentationAgent, ModelGovernanceAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── ExperimentationAgent tests ──


@pytest.mark.asyncio
async def test_experimentation_no_experiment(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExperimentationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()
    assert result["decision"]["action"] == "no_experiment"


@pytest.mark.asyncio
async def test_experimentation_with_results(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExperimentationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "experiment_name": "Prompt A vs B",
        "metric": "latency",
        "results": [
            {"name": "control", "mean": 100, "std": 10, "n": 500},
            {"name": "variant", "mean": 95, "std": 10, "n": 500},
        ],
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["decision"]["action"] == "analyze_experiment"
    assert "stats" in result["decision"]


@pytest.mark.asyncio
async def test_experimentation_uses_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ExperimentationAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"experiment_name": "Test", "results": []}
    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "sonnet" in call_kwargs.kwargs.get("model", "")


# ── ModelGovernanceAgent tests ──


@pytest.mark.asyncio
async def test_governance_check_usage(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ModelGovernanceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "check_usage", "budget_used_pct": 50.0})
    await event_bus.stop()
    assert result["decision"]["action"] == "check_usage"
    assert result["decision"]["budget_warning"] is False


@pytest.mark.asyncio
async def test_governance_budget_warning(mock_llm: LLMGateway, event_bus: EventBus):
    """Budget > 80% should trigger warning."""
    agent = ModelGovernanceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "check_usage", "budget_used_pct": 85.0})
    await event_bus.stop()
    assert result["decision"]["budget_warning"] is True


@pytest.mark.asyncio
async def test_governance_switch_model(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ModelGovernanceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "switch_model", "model_name": "sonnet"})
    await event_bus.stop()
    assert result["decision"]["action"] == "switch_model_production"


@pytest.mark.asyncio
async def test_governance_update_config(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ModelGovernanceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "update_config"})
    await event_bus.stop()
    assert result["decision"]["action"] == "update_model_config"


@pytest.mark.asyncio
async def test_governance_uses_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ModelGovernanceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    await agent.run(ctx, input_data={"action_type": "check_usage"})
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "haiku" in call_kwargs.kwargs.get("model", "")
