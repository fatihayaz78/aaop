"""Knowledge Base API router — /knowledge prefix."""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone
from typing import Any
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])

class DocumentCreate(BaseModel):
    title: str
    content: str
    collection: str = "platform"

class DocumentDelete(BaseModel):
    collection: str

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "knowledge_base"}

@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    from apps.knowledge_base.seed import get_all_docs
    docs = get_all_docs()
    return {
        "total_documents": sum(len(v) for v in docs.values()),
        "collections": {k: len(v) for k, v in docs.items()},
        "recent_searches": random.randint(10, 50),
        "last_indexed": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/search")
async def search(q: str = "", collection: str | None = None, limit: int = 5,
    ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    if not q:
        return {"results": [], "query": q}
    from apps.knowledge_base.seed import search_docs
    results = search_docs(q, collection, limit)
    return {"results": results, "query": q}

@router.get("/documents")
async def list_documents(collection: str = "incidents", limit: int = 20,
    ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    from apps.knowledge_base.seed import get_all_docs
    docs = get_all_docs().get(collection, [])
    items = [{"id": d["id"], "title": d["title"], "content": d["content"], "content_preview": d["content"][:150], "collection": collection} for d in docs[:limit]]
    return {"items": items, "total": len(docs)}

@router.post("/documents")
async def create_document(payload: DocumentCreate, ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    logger.info("document_created", id=doc_id, collection=payload.collection)
    return {"id": doc_id, "title": payload.title, "collection": payload.collection}

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"approval_required": True, "message": "Document deletion requires admin approval. Contact platform team."}

@router.get("/collections")
async def list_collections(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    from apps.knowledge_base.seed import get_all_docs
    docs = get_all_docs()
    return {
        "collections": list(docs.keys()),
        "counts": {k: len(v) for k, v in docs.items()},
    }
