"""Live Intelligence API router — /live prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/live", tags=["live-intelligence"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "live_intelligence"}


@router.get("/events")
async def list_events(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/external/drm")
async def drm_status(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, str]:
    return {"widevine": "healthy", "fairplay": "healthy", "playready": "healthy"}
