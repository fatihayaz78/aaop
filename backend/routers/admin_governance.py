"""Admin & Governance API router — /admin prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-governance"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "admin_governance"}


@router.get("/tenants")
async def list_tenants(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/modules")
async def module_configs(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/audit")
async def audit_log(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    return []


@router.get("/compliance")
async def compliance(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "report": None}


@router.get("/usage")
async def usage_stats(ctx: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    return {"tenant_id": ctx.tenant_id, "stats": None}
