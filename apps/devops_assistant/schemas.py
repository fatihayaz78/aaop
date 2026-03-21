"""DevOps Assistant Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ServiceHealth(BaseModel):
    service: str
    status: str = "healthy"  # healthy, degraded, down, unknown
    latency_ms: int = 0
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


class Deployment(BaseModel):
    deployment_id: str = Field(default_factory=lambda: f"DEP-{uuid4().hex[:8]}")
    tenant_id: str
    service: str
    version: str
    status: str = "pending"  # pending, deploying, deployed, failed, rolled_back
    deployed_by: str = ""
    notes: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommandSuggestion(BaseModel):
    command: str
    description: str = ""
    is_dangerous: bool = False
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH


class RunbookExecution(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"RBX-{uuid4().hex[:8]}")
    tenant_id: str
    runbook_id: str
    runbook_title: str = ""
    status: str = "pending"  # pending, approved, running, completed, failed
    steps_completed: int = 0
    total_steps: int = 0
    output: str = ""
