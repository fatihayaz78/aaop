"""Log Analyzer Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class LogProject(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    name: str
    sub_module: str
    config_json: dict[str, Any] | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogSource(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    project_id: str
    source_type: str
    config_json: dict[str, Any] | None = None
    last_fetch: datetime | None = None
    status: str = "idle"


class FetchJob(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    project_id: str
    sub_module: str
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class AnalysisResult(BaseModel):
    analysis_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    project_id: str
    sub_module: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    total_requests: int = 0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    avg_ttfb_ms: float = 0.0
    p99_ttfb_ms: float = 0.0
    top_errors: list[dict[str, Any]] = Field(default_factory=list)
    edge_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    agent_summary: str | None = None
    report_path: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SubModuleStatus(BaseModel):
    name: str
    display_name: str
    is_active: bool = True
    last_run: datetime | None = None
    status: str = "idle"
