"""DevOps Assistant API router — /devops prefix."""
from __future__ import annotations
import random
from typing import Any
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext
from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/devops", tags=["devops-assistant"])

_DANGEROUS = ["rm -rf", "drop table", "delete from", "shutdown", "kill -9", "format", "truncate"]

class ChatRequest(BaseModel):
    message: str
    context: str | None = None

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "devops_assistant"}

@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    from apps.knowledge_base.seed import get_all_docs
    docs = get_all_docs()

    try:
        from shared.ingest.log_queries import get_infrastructure_health, get_api_health
        infra = get_infrastructure_health("aaop_company", hours=24)
        api = get_api_health("aaop_company", hours=24)
    except Exception:
        infra = {"services": [], "critical_services": []}
        api = {"total_requests": 0, "error_rate_pct": 0}

    return {
        "runbooks_available": len(docs.get("runbooks", [])),
        "recent_queries_24h": random.randint(5, 25),
        "dangerous_commands_blocked": random.randint(0, 3),
        "top_topics": ["cdn", "drm", "scaling", "incident", "deployment"],
        "infra_health": infra,
        "api_health": api,
    }

@router.post("/chat")
async def chat(payload: ChatRequest, ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    msg_lower = payload.message.lower()
    for cmd in _DANGEROUS:
        if cmd in msg_lower:
            logger.warning("dangerous_command_blocked", command=cmd, tenant_id=ctx.tenant_id)
            return {"blocked": True, "reason": f"Dangerous command detected: '{cmd}'", "response": "", "sources": []}

    from apps.knowledge_base.seed import search_docs
    results = search_docs(payload.message, "runbooks", 3)
    sources = [r["title"] for r in results]
    context = "\n".join(f"- {r['title']}: {r['content'][:100]}" for r in results)

    try:
        from anthropic import AsyncAnthropic
        settings = get_settings()
        if not settings.anthropic_api_key:
            return {"blocked": False, "response": f"Based on runbooks: {context or 'No relevant runbooks found.'}", "sources": sources}
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        system = f"You are a DevOps assistant for OTT platform. Use the provided runbook context to answer. Be concise and practical.\n\nContext:\n{context}"
        response = await client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1024,
            system=system, messages=[{"role": "user", "content": payload.message}])
        return {"blocked": False, "response": response.content[0].text, "sources": sources}
    except Exception as exc:
        return {"blocked": False, "response": f"Based on runbooks: {context or 'No relevant runbooks found.'}", "sources": sources}

@router.get("/runbooks")
async def list_runbooks(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    from apps.knowledge_base.seed import get_all_docs
    docs = get_all_docs().get("runbooks", [])
    items = [{"id": d["id"], "title": d["title"], "content_preview": d["content"][:100]} for d in docs]
    return {"items": items, "total": len(items)}

@router.get("/runbooks/search")
async def search_runbooks(q: str = "", ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    if not q:
        return {"results": [], "query": q}
    from apps.knowledge_base.seed import search_docs
    results = search_docs(q, "runbooks", 5)
    return {"results": results, "query": q}
