"""Tests for Knowledge Base schemas."""

from __future__ import annotations

from apps.knowledge_base.schemas import Document, DocumentChunk, IngestResult, SearchResult


def test_document_defaults():
    d = Document(tenant_id="t1", collection="incidents", title="CDN Outage")
    assert d.doc_id.startswith("DOC-")
    assert d.content == ""


def test_document_chunk():
    c = DocumentChunk(doc_id="d1", content="Some chunk text", chunk_index=0, token_count=100)
    assert c.chunk_id.startswith("CHK-")


def test_search_result():
    s = SearchResult(doc_id="d1", collection="runbooks", title="Restart CDN", relevance_score=0.85)
    assert s.relevance_score == 0.85


def test_ingest_result():
    r = IngestResult(doc_id="d1", collection="incidents", chunks_created=3)
    assert r.status == "indexed"
