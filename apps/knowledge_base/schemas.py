"""Knowledge Base Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Document(BaseModel):
    doc_id: str = Field(default_factory=lambda: f"DOC-{uuid4().hex[:12]}")
    tenant_id: str
    collection: str  # incidents, runbooks, platform
    title: str
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_app: str = ""
    source_event_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: f"CHK-{uuid4().hex[:8]}")
    doc_id: str
    content: str
    chunk_index: int = 0
    token_count: int = 0


class SearchResult(BaseModel):
    doc_id: str
    collection: str
    title: str
    content: str = ""
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResult(BaseModel):
    doc_id: str
    collection: str
    chunks_created: int = 0
    status: str = "indexed"  # indexed, failed
