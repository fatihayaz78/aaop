"""Multi-tenant data models — Tenant / Service hierarchy (S-MT-01)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenantBase(BaseModel):
    id: str
    name: str
    sector: str
    status: str = "active"


class ServiceBase(BaseModel):
    id: str
    tenant_id: str
    name: str
    duckdb_schema: str
    sector_override: str | None = None
    status: str = "active"


class TenantWithServices(TenantBase):
    services: list[ServiceBase] = Field(default_factory=list)
