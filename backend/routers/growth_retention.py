"""Growth & Retention API router — /growth prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/growth", tags=["growth-retention"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "growth_retention"}


@router.get("/retention")
async def retention_dashboard(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "scores": []}


@router.get("/churn-risk")
async def churn_risk(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/segments")
async def segments(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.post("/query")
async def data_analyst_query(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "result": None}
