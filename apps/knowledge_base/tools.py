"""Knowledge Base tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.knowledge_base.config import KnowledgeBaseConfig
from apps.knowledge_base.schemas import Document, DocumentChunk, IngestResult, SearchResult

logger = structlog.get_logger(__name__)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks by approximate token count (4 chars ≈ 1 token)."""
    chars_per_token = 4
    chunk_chars = chunk_size * chars_per_token
    overlap_chars = overlap * chars_per_token

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap_chars
        if start >= len(text):
            break
    return chunks or [text] if text.strip() else []


# ── LOW risk tools ──────────────────────────────────────


async def semantic_search(
    tenant_id: str, query: str, collection: str, chroma: Any,
) -> list[SearchResult]:
    """Search ChromaDB collection. Risk: LOW."""
    config = KnowledgeBaseConfig()
    results = chroma.query(
        collection_name=collection,
        query_text=query,
        n_results=config.search_top_k,
        where={"tenant_id": tenant_id},
    )
    search_results: list[SearchResult] = []
    if results and results.get("documents"):
        docs = results["documents"][0] if results["documents"] else []
        ids = results["ids"][0] if results.get("ids") else []
        distances = results["distances"][0] if results.get("distances") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []

        for i, doc in enumerate(docs):
            score = 1.0 - (distances[i] if i < len(distances) else 1.0)
            if score < config.min_relevance_score:
                continue
            meta = metadatas[i] if i < len(metadatas) else {}
            search_results.append(SearchResult(
                doc_id=ids[i] if i < len(ids) else "",
                collection=collection,
                title=meta.get("title", ""),
                content=doc,
                relevance_score=round(score, 4),
                metadata=meta,
            ))
    logger.info("semantic_search", tenant_id=tenant_id, collection=collection, results=len(search_results))
    return search_results


async def ingest_document(
    tenant_id: str, doc: Document, chroma: Any,
) -> IngestResult:
    """Ingest document into ChromaDB with chunking. Risk: LOW."""
    config = KnowledgeBaseConfig()
    chunks = chunk_text(doc.content, config.chunk_size_tokens, config.chunk_overlap_tokens)

    for i, chunk_text_content in enumerate(chunks):
        chunk = DocumentChunk(
            doc_id=doc.doc_id, content=chunk_text_content,
            chunk_index=i, token_count=len(chunk_text_content) // 4,
        )
        chroma.add(
            collection_name=doc.collection,
            documents=[chunk.content],
            ids=[chunk.chunk_id],
            metadatas=[{
                "tenant_id": tenant_id,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "chunk_index": i,
                "source_app": doc.source_app,
                "source_event_id": doc.source_event_id,
            }],
        )

    logger.info(
        "document_ingested",
        tenant_id=tenant_id, doc_id=doc.doc_id,
        collection=doc.collection, chunks=len(chunks),
    )
    return IngestResult(doc_id=doc.doc_id, collection=doc.collection, chunks_created=len(chunks))


async def get_related_incidents(
    tenant_id: str, query: str, chroma: Any,
) -> list[SearchResult]:
    """Search incidents collection specifically. Risk: LOW."""
    return await semantic_search(tenant_id, query, "incidents", chroma)


async def get_runbook(
    tenant_id: str, query: str, chroma: Any,
) -> list[SearchResult]:
    """Search runbooks collection. Risk: LOW."""
    return await semantic_search(tenant_id, query, "runbooks", chroma)


# ── HIGH risk tools ─────────────────────────────────────


async def delete_document(
    tenant_id: str, doc_id: str, collection: str,
) -> dict:
    """Delete document from ChromaDB. Risk: HIGH (approval_required)."""
    logger.warning(
        "document_delete_requested",
        tenant_id=tenant_id, doc_id=doc_id, collection=collection,
    )
    return {
        "status": "approval_required",
        "doc_id": doc_id,
        "collection": collection,
    }
