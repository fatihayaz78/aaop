"""Ops Center Pydantic v2 models — incidents, RCA, decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.schemas.base_event import SeverityLevel


class IncidentCreate(BaseModel):
    tenant_id: str
    severity: SeverityLevel
    title: str
    description: str
    source_app: str = ""
    affected_services: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    correlation_ids: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"INC-{uuid4().hex[:12]}")
    tenant_id: str
    severity: SeverityLevel
    title: str
    description: str = ""
    status: str = "open"
    source_app: str = ""
    affected_services: list[str] = Field(default_factory=list)
    metrics_at_time: dict[str, Any] = Field(default_factory=dict)
    correlation_ids: list[str] = Field(default_factory=list)
    rca_id: str | None = None
    mttr_seconds: int | None = None
    summary_tr: str = ""
    detail_en: str = ""
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RCARequest(BaseModel):
    incident_id: str
    tenant_id: str


class RCAResult(BaseModel):
    rca_id: str = Field(default_factory=lambda: f"RCA-{uuid4().hex[:12]}")
    incident_id: str
    tenant_id: str
    root_cause: str = ""
    contributing_factors: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary_tr: str = ""
    detail_en: str = ""
    confidence_score: float = 0.0
    correlation_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OpsMetrics(BaseModel):
    tenant_id: str
    active_incidents: int = 0
    resolved_last_24h: int = 0
    avg_mttr_seconds: float = 0.0
    p0_p1_count: int = 0
    agent_decisions_24h: int = 0
