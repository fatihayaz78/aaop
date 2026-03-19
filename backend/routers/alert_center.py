"""Alert Center API router — /alerts prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["alert-center"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "alert_center"}


@router.get("")
async def list_alerts(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/rules")
async def list_rules(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/channels")
async def list_channels(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []
