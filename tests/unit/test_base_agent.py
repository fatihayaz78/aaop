"""Tests for shared/agents/base_agent.py."""

from __future__ import annotations

from typing import Any

import pytest

from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


class MockAgent(BaseAgent):
    """Concrete agent for testing."""

    app_name = "test_agent"

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        return {"loaded": True}

    async def reason(self, state: AgentState) -> dict[str, Any]:
        return {"action": "test_action", "confidence": 0.95}

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        return [{"tool": "test_tool", "result": "ok"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        return {"saved": True}


@pytest.mark.asyncio
async def test_agent_run(mock_llm_gateway: LLMGateway, event_bus: EventBus):
    agent = MockAgent(llm_gateway=mock_llm_gateway, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    result = await agent.run(ctx)
    assert result["context_data"]["loaded"] is True
    assert result["llm_response"]["action"] == "test_action"
    assert len(result["tool_results"]) == 1
    assert result["decision"]["saved"] is True
    assert result["error"] is None


@pytest.mark.asyncio
async def test_agent_error_handling(mock_llm_gateway: LLMGateway, event_bus: EventBus):
    class FailAgent(BaseAgent):
        app_name = "fail_agent"

        async def load_context(self, state: AgentState) -> dict[str, Any]:
            msg = "context load failed"
            raise RuntimeError(msg)

        async def reason(self, state: AgentState) -> dict[str, Any]:
            return {}

        async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
            return []

        async def update_memory(self, state: AgentState) -> dict[str, Any]:
            return {}

    agent = FailAgent(llm_gateway=mock_llm_gateway, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    result = await agent.run(ctx)
    assert result["error"] is not None
    assert "context load failed" in result["error"]


def test_graph_nodes(mock_llm_gateway: LLMGateway, event_bus: EventBus):
    agent = MockAgent(llm_gateway=mock_llm_gateway, event_bus=event_bus)
    nodes = agent.graph.nodes
    assert "context_loader" in nodes
    assert "reasoning" in nodes
    assert "tool_execution" in nodes
    assert "memory_update" in nodes
