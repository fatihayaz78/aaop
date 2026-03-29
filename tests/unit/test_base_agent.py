"""Tests for shared/agents/base_agent.py — LangGraph 4-step cycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.agents.base_agent import AgentState, BaseAgent


# ── Concrete test agent ──

class ConcreteAgent(BaseAgent):
    app_name = "test_app"

    def __init__(self, **kwargs):
        from shared.event_bus import EventBus
        super().__init__(llm_gateway=MagicMock(), event_bus=EventBus())

    def get_tools(self):
        return [
            {"name": "tool_low", "risk_level": "LOW", "func": AsyncMock(return_value={"ok": True})},
            {"name": "tool_medium", "risk_level": "MEDIUM", "func": AsyncMock(return_value={"routed": True})},
            {"name": "tool_high", "risk_level": "HIGH", "func": AsyncMock(return_value={"danger": True})},
        ]

    def get_system_prompt(self):
        return "You are a test agent."

    def get_llm_model(self, severity=None):
        if severity in ("P0", "P1"):
            return "claude-opus-4-20250514"
        return "claude-sonnet-4-20250514"


# ── Tests ──


class TestContextLoaderNode:
    @pytest.mark.asyncio
    async def test_handles_all_clients_unavailable(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {"msg": "test"}, "context": {},
            "reasoning": {}, "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        with patch("backend.dependencies._redis", None), \
             patch("backend.dependencies._duckdb", None):
            result = await agent._context_loader_node(state)
        assert "context" in result
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_gets_redis_data(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {}, "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        mock_redis = MagicMock()
        mock_redis._client = True
        mock_redis.get_json = AsyncMock(return_value={"cached": True})
        with patch("backend.dependencies._redis", mock_redis), \
             patch("backend.dependencies._duckdb", None), \
             patch.dict("sys.modules", {}, clear=False):
            result = await agent._context_loader_node(state)
        assert result["context"].get("redis_context") == {"cached": True}


class TestReasoningNode:
    @pytest.mark.asyncio
    async def test_parses_json_response(self):
        agent = ConcreteAgent()
        agent.llm.invoke = AsyncMock(return_value={
            "content": '{"action": "create_incident", "reasoning": "CDN spike", "tool_to_use": "tool_low", "parameters": {}}',
            "model": "claude-sonnet-4-20250514", "input_tokens": 100, "output_tokens": 50,
        })
        state: AgentState = {
            "tenant_id": "t1", "input": {"severity": "P2"}, "context": {},
            "reasoning": {}, "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._reasoning_node(state)
        assert result["reasoning"]["action"] == "create_incident"
        assert result["reasoning"]["tool_to_use"] == "tool_low"

    @pytest.mark.asyncio
    async def test_handles_llm_error(self):
        agent = ConcreteAgent()
        agent.llm.invoke = AsyncMock(side_effect=Exception("API timeout"))
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {}, "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._reasoning_node(state)
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_skips_on_prior_error(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {}, "tool_results": {}, "output": {},
            "approval_required": False, "error": "prior error",
        }
        result = await agent._reasoning_node(state)
        assert result["reasoning"] == {}


class TestToolExecutionNode:
    @pytest.mark.asyncio
    async def test_low_risk_auto_executes(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {"tool_to_use": "tool_low", "parameters": {}},
            "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._tool_execution_node(state)
        assert result["tool_results"]["status"] == "success"
        assert result["approval_required"] is False

    @pytest.mark.asyncio
    async def test_high_risk_requires_approval(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {"tool_to_use": "tool_high", "parameters": {}},
            "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._tool_execution_node(state)
        assert result["approval_required"] is True
        assert result["tool_results"]["status"] == "approval_required"

    @pytest.mark.asyncio
    async def test_no_tool_specified(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {"tool_to_use": None},
            "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._tool_execution_node(state)
        assert result["tool_results"]["status"] == "no_tool"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {"tool_to_use": "nonexistent"},
            "tool_results": {}, "output": {},
            "approval_required": False, "error": None,
        }
        result = await agent._tool_execution_node(state)
        assert result["tool_results"]["status"] == "not_found"


class TestMemoryUpdateNode:
    @pytest.mark.asyncio
    async def test_builds_output(self):
        agent = ConcreteAgent()
        state: AgentState = {
            "tenant_id": "t1", "input": {"severity": "P2"}, "context": {},
            "reasoning": {"action": "analyze", "reasoning": "All clear", "tool_to_use": "none"},
            "tool_results": {"status": "success"}, "output": {},
            "approval_required": False, "error": None,
        }
        with patch("backend.dependencies._duckdb", None), \
             patch("backend.dependencies._redis", None):
            result = await agent._memory_update_node(state)
        assert "decision_id" in result["output"]
        assert result["output"]["app"] == "test_app"

    @pytest.mark.asyncio
    async def test_survives_duckdb_failure(self):
        agent = ConcreteAgent()
        mock_duck = MagicMock()
        mock_duck.execute = MagicMock(side_effect=Exception("DB error"))
        state: AgentState = {
            "tenant_id": "t1", "input": {}, "context": {},
            "reasoning": {"action": "test"}, "tool_results": {},
            "output": {}, "approval_required": False, "error": None,
        }
        with patch("backend.dependencies._duckdb", mock_duck), \
             patch("backend.dependencies._redis", None):
            result = await agent._memory_update_node(state)
        assert "decision_id" in result["output"]


class TestModelRouting:
    def test_p0_opus(self):
        agent = ConcreteAgent()
        assert agent.get_llm_model("P0") == "claude-opus-4-20250514"

    def test_p2_sonnet(self):
        agent = ConcreteAgent()
        assert agent.get_llm_model("P2") == "claude-sonnet-4-20250514"

    def test_none_sonnet(self):
        agent = ConcreteAgent()
        assert agent.get_llm_model(None) == "claude-sonnet-4-20250514"


class TestGraphCompilation:
    def test_graph_compiles(self):
        agent = ConcreteAgent()
        assert agent._graph is not None
