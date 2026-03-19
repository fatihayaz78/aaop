"""Ops Center API router — /ops prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from apps.ops_center.schemas import OpsMetrics
from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ops", tags=["ops-center"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "ops_center"}


@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant_context)) -> OpsMetrics:
    return OpsMetrics(tenant_id=ctx.tenant_id)


@router.get("/incidents")
async def list_incidents(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"incident_id": incident_id, "tenant_id": ctx.tenant_id, "status": "not_found"}
