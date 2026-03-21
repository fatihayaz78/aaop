"""AI Lab API router — /ai-lab prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ai-lab", tags=["ai-lab"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ai_lab"}


@router.get("/experiments")
async def list_experiments(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/models")
async def model_registry(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/cost")
async def cost_tracker(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "metrics": None}
