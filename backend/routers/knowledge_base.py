"""Knowledge Base API router — /knowledge prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "knowledge_base"}


@router.get("/search")
async def search(query: str = "", ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/incidents")
async def incidents(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/runbooks")
async def runbooks(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []
