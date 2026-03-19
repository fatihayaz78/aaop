"""Base event schemas, enums, and tenant context used across all apps."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SeverityLevel(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TenantContext(BaseModel):
    tenant_id: str
    user_id: str | None = None
    role: str | None = None


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    tenant_id: str
    source_app: str
    severity: SeverityLevel = SeverityLevel.P3
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
