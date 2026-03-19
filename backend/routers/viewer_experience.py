"""Viewer Experience API router — /viewer prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/viewer", tags=["viewer-experience"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "viewer_experience"}


@router.get("/qoe/metrics")
async def qoe_metrics(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/complaints")
async def list_complaints(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []
