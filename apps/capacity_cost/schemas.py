"""Capacity & Cost Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class CapacityMetrics(BaseModel):
    tenant_id: str
    metric: str  # cpu, memory, bandwidth, storage
    current_value: float = 0.0
    max_value: float = 100.0
    unit: str = "%"
    measured_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def usage_pct(self) -> float:
        if self.max_value == 0:
            return 0.0
        return (self.current_value / self.max_value) * 100


class CapacityForecast(BaseModel):
    forecast_id: str = Field(default_factory=lambda: f"FCT-{uuid4().hex[:12]}")
    tenant_id: str
    metric: str
    current_pct: float
    predicted_pct: float
    horizon_hours: int = 24
    trend: str = "stable"  # stable, growing, declining
    breach_estimated_hours: int | None = None
    confidence: float = 0.0


class ThresholdBreach(BaseModel):
    tenant_id: str
    metric: str
    current_pct: float
    threshold_pct: float
    level: str  # warn, critical
    message: str = ""


class CostReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"COST-{uuid4().hex[:8]}")
    tenant_id: str
    period: str  # daily, weekly, monthly
    total_cost: float = 0.0
    currency: str = "USD"
    breakdown: dict[str, float] = Field(default_factory=dict)
    cost_per_viewer: float = 0.0


class ScaleAction(BaseModel):
    action_id: str = Field(default_factory=lambda: f"SCALE-{uuid4().hex[:8]}")
    tenant_id: str
    resource: str  # cdn, compute, storage
    action_type: str  # scale_up, scale_down
    scale_factor: float = 1.0
    reason: str = ""
    status: str = "pending"  # pending, approved, executed, failed


class AutomationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: f"JOB-{uuid4().hex[:8]}")
    tenant_id: str
    job_type: str  # scale, cleanup, optimize
    status: str = "pending"  # pending, approved, running, completed, failed
    config: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
