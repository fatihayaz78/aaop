"""Knowledge Base agent — KnowledgeBaseAgent (M15).

Haiku for fast Q&A. Auto-indexes incident_created and rca_completed events.
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.knowledge_base.config import KnowledgeBaseConfig
from apps.knowledge_base.prompts import KB_SYSTEM_PROMPT
from apps.knowledge_base.schemas import Document
from apps.knowledge_base.tools import ingest_document
import apps.knowledge_base.tools as tools
from shared.agents.base_agent import AgentState, BaseAgent
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent

logger = structlog.get_logger(__name__)


# ── Tool wrappers ───────────────────────────────────────────────

async def _semantic_search(tenant_id: str, query: str = "", **_: Any) -> list:
    return []

async def _ingest_document(tenant_id: str, **_: Any) -> dict:
    return {"status": "ingested"}

async def _get_related_incidents(tenant_id: str, **_: Any) -> list:
    return []

async def _get_runbook(tenant_id: str, **_: Any) -> dict:
    return {}

async def _delete_document(tenant_id: str, doc_id: str = "", **_: Any) -> dict:
    return {"status": "approval_required", "doc_id": doc_id}


# ── KnowledgeBaseAgent ──────────────────────────────────────────

class KnowledgeBaseAgent(BaseAgent):
    """M15 — Knowledge Base. Haiku for fast Q&A. Auto-indexes incidents + RCAs."""

    app_name = "knowledge_base"

    def __init__(self, chroma: Any = None, **kwargs: Any) -> None:
        self._config = KnowledgeBaseConfig()
        self._chroma = chroma
        super().__init__(**kwargs)

    def subscribe_events(self) -> None:
        """Register: incident_created, rca_completed (auto-index)."""
        self.event_bus.subscribe(EventType.INCIDENT_CREATED, self._on_event)
        self.event_bus.subscribe(EventType.RCA_COMPLETED, self._on_event)

    async def _on_event(self, event: BaseEvent) -> None:
        try:
            payload = event.payload if isinstance(event.payload, dict) else {}
            payload["event_type"] = event.event_type
            payload["event_payload"] = payload.copy()
            await self.invoke(tenant_id=event.tenant_id or "aaop_company", input_data=payload)
        except Exception as exc:
            logger.error("event_handler_error", app=self.app_name, event=event.event_type, error=str(exc))

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "semantic_search", "risk_level": "LOW", "func": _semantic_search},
            {"name": "ingest_document", "risk_level": "LOW", "func": _ingest_document},
            {"name": "get_related_incidents", "risk_level": "LOW", "func": _get_related_incidents},
            {"name": "get_runbook", "risk_level": "LOW", "func": _get_runbook},
            {"name": "delete_document", "risk_level": "HIGH", "func": _delete_document},
        ]

    def get_system_prompt(self) -> str:
        return KB_SYSTEM_PROMPT

    def get_llm_model(self, severity: str | None = None) -> str:
        return "claude-haiku-4-5-20251001"

    async def invoke(self, tenant_id: str, input_data: dict[str, Any]) -> dict[str, Any]:
        action_type = input_data.get("action_type", "search")
        event_type = input_data.get("event_type")

        # Auto-index on EventBus events
        if event_type in (EventType.INCIDENT_CREATED.value, "incident_created"):
            payload = input_data.get("event_payload", {})
            indexed = await self._auto_index(tenant_id, "auto_index_incident", payload)
            return {"app": self.app_name, "tenant_id": tenant_id,
                    "action": "auto_index_incident", "indexed": indexed, "query": "", "collection": "incidents"}

        if event_type in (EventType.RCA_COMPLETED.value, "rca_completed"):
            payload = input_data.get("event_payload", {})
            indexed = await self._auto_index(tenant_id, "auto_index_rca", payload)
            return {"app": self.app_name, "tenant_id": tenant_id,
                    "action": "auto_index_rca", "indexed": indexed, "query": "", "collection": "incidents"}

        if action_type == "delete":
            input_data["_mapped_action"] = "delete_document"
            return await super().invoke(tenant_id, input_data)

        # Search — need query
        query = input_data.get("query", "")
        if not query:
            return {"app": self.app_name, "tenant_id": tenant_id,
                    "action": "no_query", "indexed": False, "query": "", "collection": ""}

        input_data["_mapped_action"] = "search"
        return await super().invoke(tenant_id, input_data)

    async def _auto_index(self, tenant_id: str, action: str, payload: dict) -> bool:
        if not self._chroma:
            return False
        doc = Document(
            tenant_id=tenant_id, collection="incidents",
            title=payload.get("title", f"Auto-indexed {action}"),
            content=str(payload), source_app="ops_center",
            source_event_id=payload.get("incident_id", payload.get("rca_id", "")),
            metadata={"auto_indexed": True, "event_type": action},
        )
        await ingest_document(tenant_id, doc, self._chroma)
        return True

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        result = await super()._memory_update_node(state)
        input_data = state.get("input", {})

        output = result.get("output", {})
        output["action"] = input_data.get("_mapped_action", "search")
        output["query"] = input_data.get("query", "")
        output["collection"] = input_data.get("collection", "incidents")

        return {**result, "output": output}
