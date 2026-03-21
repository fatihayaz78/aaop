"""Capacity & Cost API router — /capacity prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/capacity", tags=["capacity-cost"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "capacity_cost"}


@router.get("/forecast")
async def forecast(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/usage")
async def current_usage(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "metrics": []}


@router.get("/jobs")
async def automation_jobs(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/cost")
async def cost_analysis(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "report": None}
