"""Tests for Knowledge Base tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.knowledge_base.schemas import Document
from apps.knowledge_base.tools import (
    chunk_text,
    delete_document,
    get_related_incidents,
    get_runbook,
    ingest_document,
    semantic_search,
)

# ── Chunking ──


def test_chunk_text_single():
    text = "Short text"
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "Short text"


def test_chunk_text_multiple():
    text = "x" * 5000  # ~1250 tokens at 4 chars/token
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) > 1


def test_chunk_text_empty():
    chunks = chunk_text("", chunk_size=500, overlap=50)
    assert chunks == []


def test_chunk_text_overlap():
    text = "a" * 4000
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    # Second chunk should start before the end of the first
    assert len(chunks) >= 2


# ── Semantic search ──


@pytest.mark.asyncio
async def test_semantic_search(mock_chroma: MagicMock):
    results = await semantic_search("t1", "CDN error", "incidents", mock_chroma)
    assert len(results) == 1
    assert results[0].relevance_score > 0.3


@pytest.mark.asyncio
async def test_semantic_search_empty(mock_chroma: MagicMock):
    mock_chroma.query = MagicMock(return_value={"documents": [], "ids": [], "distances": [], "metadatas": []})
    results = await semantic_search("t1", "nothing", "incidents", mock_chroma)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_semantic_search_low_relevance(mock_chroma: MagicMock):
    mock_chroma.query = MagicMock(return_value={
        "documents": [["irrelevant"]],
        "ids": [["d1"]],
        "distances": [[0.95]],  # high distance = low relevance
        "metadatas": [[{"title": "No Match"}]],
    })
    results = await semantic_search("t1", "test", "incidents", mock_chroma)
    assert len(results) == 0  # below min_relevance_score


# ── Ingest ──


@pytest.mark.asyncio
async def test_ingest_document(mock_chroma: MagicMock):
    doc = Document(tenant_id="t1", collection="incidents", title="Test Incident", content="Some content here")
    result = await ingest_document("t1", doc, mock_chroma)
    assert result.status == "indexed"
    assert result.chunks_created >= 1
    mock_chroma.add.assert_called()


@pytest.mark.asyncio
async def test_ingest_large_document(mock_chroma: MagicMock):
    doc = Document(tenant_id="t1", collection="runbooks", title="Big Runbook", content="x" * 10000)
    result = await ingest_document("t1", doc, mock_chroma)
    assert result.chunks_created > 1


# ── Related incidents / runbooks ──


@pytest.mark.asyncio
async def test_get_related_incidents(mock_chroma: MagicMock):
    results = await get_related_incidents("t1", "CDN", mock_chroma)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_runbook(mock_chroma: MagicMock):
    results = await get_runbook("t1", "restart procedure", mock_chroma)
    assert len(results) == 1


# ── HIGH risk ──


@pytest.mark.asyncio
async def test_delete_document_approval():
    result = await delete_document("t1", "doc-123", "incidents")
    assert result["status"] == "approval_required"
    assert result["doc_id"] == "doc-123"
