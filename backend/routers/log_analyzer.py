"""Log Analyzer API router — /log-analyzer prefix."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from apps.log_analyzer.schemas import SubModuleStatus
from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/log-analyzer", tags=["log-analyzer"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "module": "log_analyzer"}


@router.get("/sub-modules")
async def list_sub_modules() -> list[SubModuleStatus]:
    from apps.log_analyzer.sub_modules import SubModuleRegistry

    modules = SubModuleRegistry.list_all()
    return [
        SubModuleStatus(name=cls.name, display_name=cls.display_name)
        for cls in modules.values()
    ]


@router.get("/projects")
async def list_projects(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    # Placeholder — will read from SQLite in full implementation
    return []


@router.get("/results")
async def list_results(ctx: TenantContext = Depends(get_tenant_context)) -> list[dict[str, Any]]:
    # Placeholder — will read from DuckDB
    return []
