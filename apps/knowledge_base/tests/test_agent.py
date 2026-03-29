"""Tests for KnowledgeBaseAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.knowledge_base.agent import KnowledgeBaseAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


@pytest.mark.asyncio
async def test_kb_search(mock_llm: LLMGateway, event_bus: EventBus):
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "search", "query": "CDN error rate", "collection": "incidents"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "search"
    assert result["output"]["query"] == "CDN error rate"


@pytest.mark.asyncio
async def test_kb_no_query(mock_llm: LLMGateway, event_bus: EventBus):
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "search"})
    await event_bus.stop()
    assert result["output"]["action"] == "no_query"


@pytest.mark.asyncio
async def test_kb_auto_index_incident(mock_llm: LLMGateway, event_bus: EventBus, mock_chroma: MagicMock):
    """incident_created event should auto-index."""
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus, chroma=mock_chroma)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "event_type": "incident_created",
        "event_payload": {"incident_id": "INC-001", "title": "CDN down", "severity": "P1"},
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "auto_index_incident"
    assert result["output"]["indexed"] is True
    mock_chroma.add.assert_called()


@pytest.mark.asyncio
async def test_kb_auto_index_rca(mock_llm: LLMGateway, event_bus: EventBus, mock_chroma: MagicMock):
    """rca_completed event should auto-index."""
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus, chroma=mock_chroma)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "event_type": "rca_completed",
        "event_payload": {"rca_id": "RCA-001", "title": "Root cause: config change"},
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "auto_index_rca"
    assert result["output"]["indexed"] is True


@pytest.mark.asyncio
async def test_kb_delete_requires_approval(mock_llm: LLMGateway, event_bus: EventBus):
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"action_type": "delete", "document": {"doc_id": "doc-1"}}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["output"]["action"] == "delete_document"


@pytest.mark.asyncio
async def test_kb_uses_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    agent = KnowledgeBaseAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"query": "How to fix CDN?"}
    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "haiku" in call_kwargs.kwargs.get("model", "")
