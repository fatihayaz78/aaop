"""Knowledge Base agent — KnowledgeBaseAgent (M15)."""

from __future__ import annotations

from typing import Any

import structlog

from apps.knowledge_base.config import KnowledgeBaseConfig
from apps.knowledge_base.schemas import Document
from apps.knowledge_base.tools import ingest_document
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import SeverityLevel

logger = structlog.get_logger(__name__)


class KnowledgeBaseAgent(BaseAgent):
    """M15 — Knowledge Base. Haiku for fast Q&A. Auto-indexes incidents and RCAs."""

    app_name = "knowledge_base"

    def __init__(self, chroma: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = KnowledgeBaseConfig()
        self._chroma = chroma

    async def load_context(self, state: AgentState) -> dict[str, Any]:
        tenant_id = state["tenant_context"].get("tenant_id", "")
        input_data = state.get("context_data", {})
        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "action_type": input_data.get("action_type", "search"),
            "query": input_data.get("query", ""),
            "collection": input_data.get("collection", "incidents"),
            "document": input_data.get("document"),
            "event_type": input_data.get("event_type"),
            "event_payload": input_data.get("event_payload", {}),
        }
        logger.info("kb_context_loaded", tenant_id=tenant_id, action=context["action_type"])
        return context

    async def reason(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        action_type = ctx.get("action_type", "search")
        event_type = ctx.get("event_type")

        # Auto-index on EventBus events
        if event_type in (EventType.INCIDENT_CREATED.value, "incident_created"):
            return {
                "action": "auto_index_incident",
                "event_payload": ctx.get("event_payload", {}),
                "collection": "incidents",
            }
        if event_type in (EventType.RCA_COMPLETED.value, "rca_completed"):
            return {
                "action": "auto_index_rca",
                "event_payload": ctx.get("event_payload", {}),
                "collection": "incidents",
            }

        if action_type == "ingest":
            return {"action": "ingest_document", "document": ctx.get("document")}

        if action_type == "delete":
            return {"action": "delete_document", "doc_id": ctx.get("document", {}).get("doc_id", "")}

        # Search — use Haiku for fast Q&A
        query = ctx.get("query", "")
        if not query:
            return {"action": "no_query", "reason": "No query provided"}

        from apps.knowledge_base.prompts import SEARCH_PROMPT

        prompt = SEARCH_PROMPT.format(
            query=query, collection=ctx.get("collection", "incidents"),
            tenant_id=ctx.get("tenant_id", ""),
        )
        response = await self.llm.invoke(prompt, severity=SeverityLevel.P3)

        return {
            "action": "search",
            "query": query,
            "collection": ctx.get("collection", "incidents"),
            "summary": response["content"],
            "model_used": response["model"],
        }

    async def execute_tools(self, state: AgentState) -> list[dict[str, Any]]:
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")

        if action == "no_query":
            return [{"tool": "no_query", "risk_level": "LOW"}]
        if action == "search":
            return [{"tool": "semantic_search", "risk_level": "LOW"}]
        if action in ("auto_index_incident", "auto_index_rca"):
            return [{"tool": "ingest_document", "risk_level": "LOW"}]
        if action == "ingest_document":
            return [{"tool": "ingest_document", "risk_level": "LOW"}]
        if action == "delete_document":
            return [{"tool": "delete_document", "risk_level": "HIGH"}]
        return [{"tool": action, "risk_level": "LOW"}]

    async def update_memory(self, state: AgentState) -> dict[str, Any]:
        ctx = state.get("context_data", {})
        llm_resp = state.get("llm_response", {})
        action = llm_resp.get("action", "")
        tenant_id = ctx.get("tenant_id", "")

        indexed = False

        # Auto-index incident or RCA
        if action in ("auto_index_incident", "auto_index_rca") and self._chroma:
            payload = llm_resp.get("event_payload", {})
            doc = Document(
                tenant_id=tenant_id,
                collection="incidents",
                title=payload.get("title", f"Auto-indexed {action}"),
                content=str(payload),
                source_app="ops_center",
                source_event_id=payload.get("incident_id", payload.get("rca_id", "")),
                metadata={"auto_indexed": True, "event_type": action},
            )
            await ingest_document(tenant_id, doc, self._chroma)
            indexed = True

        return {
            "action": action,
            "indexed": indexed,
            "query": llm_resp.get("query", ""),
            "collection": llm_resp.get("collection", ""),
        }
