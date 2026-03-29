"""BaseAgent — LangGraph 4-step cycle with default implementations.

All 11 app agents extend this class. Each node has a default implementation
that can be overridden by subclasses.

Cycle: context_loader → reasoning → tool_execution → memory_update
"""

from __future__ import annotations

import json
import re
import time
import uuid
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from shared.event_bus import EventBus, get_event_bus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import SeverityLevel, TenantContext

logger = structlog.get_logger(__name__)


class AgentState(TypedDict, total=False):
    tenant_id: str
    tenant_context: dict[str, Any]
    input: dict[str, Any]
    context: dict[str, Any]
    reasoning: dict[str, Any]
    tool_results: dict[str, Any]
    output: dict[str, Any]
    approval_required: bool
    error: str | None


class BaseAgent:
    """Abstract base for all AAOP agents. Subclasses implement hooks + provide tools."""

    app_name: str = "base"

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.llm = llm_gateway or LLMGateway()
        self.event_bus = event_bus or get_event_bus()
        self._graph = self._build_graph()

    # ══════════════════════════════════════════════════════════════
    # Abstract methods — subclasses MUST implement
    # ══════════════════════════════════════════════════════════════

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions: [{"name": str, "risk_level": "LOW"|"MEDIUM"|"HIGH", "func": callable}]"""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the app-specific system prompt for LLM."""
        ...

    @abstractmethod
    def get_llm_model(self, severity: str | None = None) -> str:
        """Return model ID based on severity routing."""
        ...

    # ══════════════════════════════════════════════════════════════
    # Graph construction
    # ══════════════════════════════════════════════════════════════

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentState)

        graph.add_node("context_loader", self._context_loader_node)
        graph.add_node("reasoning", self._reasoning_node)
        graph.add_node("tool_execution", self._tool_execution_node)
        graph.add_node("memory_update", self._memory_update_node)

        graph.set_entry_point("context_loader")
        graph.add_edge("context_loader", "reasoning")
        graph.add_edge("reasoning", "tool_execution")

        # Conditional: if approval_required → END, else → memory_update
        def _route_after_tools(state: AgentState) -> str:
            return END if state.get("approval_required") else "memory_update"

        graph.add_conditional_edges("tool_execution", _route_after_tools)
        graph.add_edge("memory_update", END)

        return graph.compile()

    # ══════════════════════════════════════════════════════════════
    # Node 1: Context Loading (Redis → DuckDB → ChromaDB)
    # ══════════════════════════════════════════════════════════════

    async def _context_loader_node(self, state: AgentState) -> AgentState:
        context: dict[str, Any] = {}
        tenant_id = state.get("tenant_id", "")

        # 1. Redis cache
        try:
            from backend.dependencies import _redis
            if _redis and _redis._client:
                cached = await _redis.get_json(f"ctx:{tenant_id}:{self.app_name}:latest")
                if cached:
                    context["redis_context"] = cached
        except Exception as exc:
            logger.debug("context_redis_miss", app=self.app_name, error=str(exc))

        # 2. DuckDB — last 10 decisions for this app+tenant
        try:
            from backend.dependencies import _duckdb
            if _duckdb:
                decisions = _duckdb.fetch_all(
                    "SELECT * FROM shared_analytics.agent_decisions "
                    "WHERE app = ? AND tenant_id = ? ORDER BY created_at DESC LIMIT 10",
                    [self.app_name, tenant_id],
                )
                if decisions:
                    context["recent_decisions"] = decisions
        except Exception as exc:
            logger.debug("context_duckdb_miss", app=self.app_name, error=str(exc))

        # 3. ChromaDB RAG — similar past cases
        try:
            import backend.dependencies as _deps
            _chroma = getattr(_deps, "_chroma", None)
            if _chroma:
                input_text = json.dumps(state.get("input", {}), default=str)[:500]
                collection = _chroma.get_or_create_collection("incidents")
                results = collection.query(query_texts=[input_text], n_results=3)
                if results and results.get("documents"):
                    context["similar_cases"] = results["documents"][0]
        except Exception as exc:
            logger.debug("context_chroma_miss", app=self.app_name, error=str(exc))

        return {**state, "context": context}

    # ══════════════════════════════════════════════════════════════
    # Node 2: LLM Reasoning
    # ══════════════════════════════════════════════════════════════

    async def _reasoning_node(self, state: AgentState) -> AgentState:
        if state.get("error"):
            return state

        try:
            severity = state.get("input", {}).get("severity")
            model = self.get_llm_model(severity)
            system_prompt = self.get_system_prompt()
            tool_names = [t["name"] for t in self.get_tools()]

            prompt = (
                f"Input: {json.dumps(state.get('input', {}), default=str)}\n"
                f"Context: {json.dumps(state.get('context', {}), default=str)[:2000]}\n"
                f"Available tools: {tool_names}\n\n"
                "Analyze and decide. Respond with JSON: "
                '{"action": str, "reasoning": str, "tool_to_use": str|null, "parameters": dict}'
            )

            # PII scrubbing happens inside llm_gateway.invoke automatically
            response = await self.llm.invoke(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
            )

            # Parse JSON from LLM response
            content = response.get("content", "")
            try:
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                reasoning = json.loads(json_match.group()) if json_match else {
                    "action": "analyze", "reasoning": content, "tool_to_use": None, "parameters": {}
                }
            except (json.JSONDecodeError, AttributeError):
                reasoning = {"action": "analyze", "reasoning": content, "tool_to_use": None, "parameters": {}}

            reasoning["_model_used"] = response.get("model", model)
            reasoning["_tokens"] = {
                "input": response.get("input_tokens", 0),
                "output": response.get("output_tokens", 0),
            }

            return {**state, "reasoning": reasoning}

        except Exception as exc:
            logger.error("reasoning_error", app=self.app_name, error=str(exc))
            return {**state, "reasoning": {"action": "error", "reasoning": str(exc)}, "error": str(exc)}

    # ══════════════════════════════════════════════════════════════
    # Node 3: Tool Execution (LOW=auto, MEDIUM=auto+notify, HIGH=approval)
    # ══════════════════════════════════════════════════════════════

    async def _tool_execution_node(self, state: AgentState) -> AgentState:
        if state.get("error"):
            return {**state, "tool_results": {}, "approval_required": False}

        tool_name = state.get("reasoning", {}).get("tool_to_use")
        if not tool_name:
            return {**state, "tool_results": {"status": "no_tool"}, "approval_required": False}

        tools = {t["name"]: t for t in self.get_tools()}
        tool = tools.get(tool_name)

        if not tool:
            logger.warning("tool_not_found", app=self.app_name, tool=tool_name)
            return {**state, "tool_results": {"status": "not_found", "tool": tool_name}, "approval_required": False}

        risk_level = tool.get("risk_level", "LOW")

        # HIGH risk → stop, require human approval
        if risk_level == "HIGH":
            logger.info("tool_approval_required", app=self.app_name, tool=tool_name,
                        tenant_id=state.get("tenant_id"))
            return {
                **state,
                "tool_results": {"status": "approval_required", "tool": tool_name, "risk_level": "HIGH"},
                "approval_required": True,
            }

        # LOW or MEDIUM → execute
        try:
            params = state.get("reasoning", {}).get("parameters", {})
            params["tenant_id"] = state.get("tenant_id", "")
            func = tool["func"]
            result = await func(**params) if callable(func) else {"error": "not callable"}

            # MEDIUM → notify via Event Bus
            if risk_level == "MEDIUM":
                try:
                    from shared.schemas.base_event import BaseEvent
                    await self.event_bus.publish(BaseEvent(
                        event_type=f"{self.app_name}_tool_executed",
                        tenant_id=state.get("tenant_id", ""),
                        payload={"tool": tool_name, "result": str(result)[:200]},
                    ))
                except Exception:
                    pass

            return {**state, "tool_results": {"status": "success", "tool": tool_name, "result": result}, "approval_required": False}

        except Exception as exc:
            logger.error("tool_exec_error", app=self.app_name, tool=tool_name, error=str(exc))
            return {**state, "tool_results": {"status": "error", "tool": tool_name, "error": str(exc)}, "approval_required": False}

    # ══════════════════════════════════════════════════════════════
    # Node 4: Memory Update (DuckDB + Redis + output)
    # ══════════════════════════════════════════════════════════════

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        tenant_id = state.get("tenant_id", "")
        decision_id = str(uuid.uuid4())
        reasoning = state.get("reasoning", {})
        model_used = reasoning.get("_model_used", "unknown")

        # 1. Write agent decision to DuckDB
        try:
            from backend.dependencies import _duckdb
            if _duckdb:
                _duckdb.execute(
                    """INSERT INTO shared_analytics.agent_decisions
                       (decision_id, tenant_id, app, action, risk_level, approval_required,
                        llm_model_used, reasoning_summary, tools_executed,
                        confidence_score, duration_ms, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())""",
                    [
                        decision_id,
                        tenant_id,
                        self.app_name,
                        reasoning.get("action", "unknown"),
                        "HIGH" if state.get("approval_required") else "LOW",
                        state.get("approval_required", False),
                        model_used,
                        reasoning.get("reasoning", "")[:500],
                        json.dumps([reasoning.get("tool_to_use", "none")]),
                        0.85,
                        0,
                    ],
                )
        except Exception as exc:
            logger.warning("memory_duckdb_write_failed", app=self.app_name, error=str(exc))

        # 2. Update Redis context cache
        try:
            from backend.dependencies import _redis
            if _redis and _redis._client:
                cache_data = state.get("tool_results", {})
                await _redis.set_json(
                    f"ctx:{tenant_id}:{self.app_name}:latest",
                    cache_data,
                    ttl=300,
                )
        except Exception as exc:
            logger.warning("memory_redis_write_failed", app=self.app_name, error=str(exc))

        # 3. Build output
        output = {
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "app": self.app_name,
            "action": reasoning.get("action", "unknown"),
            "risk_level": "HIGH" if state.get("approval_required") else "LOW",
            "approval_required": state.get("approval_required", False),
            "llm_model_used": model_used,
            "reasoning_summary": reasoning.get("reasoning", "")[:500],
            "tools_executed": [reasoning.get("tool_to_use", "none")],
            "confidence_score": 0.85,
            "duration_ms": 0,
        }

        return {**state, "output": output}

    # ══════════════════════════════════════════════════════════════
    # Public invoke method
    # ══════════════════════════════════════════════════════════════

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the full 4-step agent cycle."""
        start = time.monotonic()

        initial_state: AgentState = {
            "tenant_id": tenant_id,
            "input": input_data,
            "context": {},
            "reasoning": {},
            "tool_results": {},
            "output": {},
            "approval_required": False,
            "error": None,
        }

        try:
            result = await self._graph.ainvoke(initial_state)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info("agent_invoke_complete", app=self.app_name,
                        tenant_id=tenant_id, duration_ms=duration_ms)

            output = result.get("output", {})
            if output:
                output["duration_ms"] = duration_ms
            return output

        except Exception as exc:
            logger.error("agent_invoke_error", app=self.app_name, error=str(exc))
            return {"error": str(exc), "app": self.app_name, "tenant_id": tenant_id}

    # Legacy compatibility
    async def run(self, tenant_context: TenantContext, input_data: dict[str, Any] | None = None) -> AgentState:
        """Legacy run method — delegates to invoke."""
        result = await self.invoke(tenant_context.tenant_id, input_data or {})
        return AgentState(
            tenant_id=tenant_context.tenant_id,
            output=result,
            approval_required=result.get("approval_required", False),
            error=result.get("error"),
        )
