"""BaseAgent — LangGraph 4-step cycle. All 11 app agents extend this."""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from shared.event_bus import EventBus, get_event_bus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)


class AgentState(TypedDict, total=False):
    tenant_context: dict[str, Any]
    context_data: dict[str, Any]
    llm_response: dict[str, Any]
    tool_results: list[dict[str, Any]]
    decision: dict[str, Any]
    error: str | None


class BaseAgent:
    """Abstract base for all AAOP agents. Subclasses implement the 4 hooks."""

    app_name: str = "base"

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.llm = llm_gateway or LLMGateway()
        self.event_bus = event_bus or get_event_bus()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("context_loader", self._context_loader_node)
        graph.add_node("reasoning", self._reasoning_node)
        graph.add_node("tool_execution", self._tool_execution_node)
        graph.add_node("memory_update", self._memory_update_node)

        graph.set_entry_point("context_loader")
        graph.add_edge("context_loader", "reasoning")
        graph.add_edge("reasoning", "tool_execution")
        graph.add_edge("tool_execution", "memory_update")
        graph.add_edge("memory_update", END)

        return graph

    async def run(self, tenant_context: TenantContext, input_data: dict[str, Any] | None = None) -> AgentState:
        """Execute the 4-step agent cycle."""
        start = time.monotonic()
        initial_state: AgentState = {
            "tenant_context": tenant_context.model_dump(),
            "context_data": input_data or {},
            "llm_response": {},
            "tool_results": [],
            "decision": {},
            "error": None,
        }
        compiled = self.graph.compile()
        result: AgentState = await compiled.ainvoke(initial_state)  # type: ignore[arg-type,assignment]
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "agent_cycle_complete",
            app=self.app_name,
            tenant_id=tenant_context.tenant_id,
            duration_ms=duration_ms,
        )
        return result

    # ── Node 1: Context Loading ──────────────────────────────

    async def _context_loader_node(self, state: AgentState) -> AgentState:
        try:
            context = await self.load_context(state)
            state["context_data"].update(context)
        except Exception as exc:
            logger.exception("context_loader_error", app=self.app_name)
            state["error"] = str(exc)
        return state

    @abstractmethod
    async def load_context(self, state: AgentState) -> dict[str, Any]:
        """Load context from Redis cache, DuckDB, ChromaDB RAG."""
        ...

    # ── Node 2: LLM Reasoning ────────────────────────────────

    async def _reasoning_node(self, state: AgentState) -> AgentState:
        if state.get("error"):
            return state
        try:
            response = await self.reason(state)
            state["llm_response"] = response
        except Exception as exc:
            logger.exception("reasoning_error", app=self.app_name)
            state["error"] = str(exc)
        return state

    @abstractmethod
    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Call LLM via gateway with severity-based routing."""
        ...

    # ── Node 3: Tool Execution ───────────────────────────────

    async def _tool_execution_node(self, state: AgentState) -> AgentState:
        if state.get("error"):
            return state
        try:
            results = await self.execute_tools(state)
            state["tool_results"] = results
        except Exception as exc:
            logger.exception("tool_execution_error", app=self.app_name)
            state["error"] = str(exc)
        return state

    @abstractmethod
    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        """Execute tools with risk_level checks. HIGH -> approval_required."""
        ...

    # ── Node 4: Memory Update ────────────────────────────────

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        if state.get("error"):
            return state
        try:
            decision = await self.update_memory(state)
            state["decision"] = decision
        except Exception as exc:
            logger.exception("memory_update_error", app=self.app_name)
            state["error"] = str(exc)
        return state

    @abstractmethod
    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        """Write AgentDecision to DuckDB, update Redis, publish events."""
        ...
