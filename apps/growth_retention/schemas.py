"""Growth & Retention Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RetentionScore(BaseModel):
    score_id: str = Field(default_factory=lambda: f"RS-{uuid4().hex[:12]}")
    tenant_id: str
    segment_id: str
    churn_risk: float  # 0.0 - 1.0
    retention_7d: float | None = None
    retention_30d: float | None = None
    factors: dict[str, Any] = Field(default_factory=dict)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerSegment(BaseModel):
    segment_id: str = Field(default_factory=lambda: f"SEG-{uuid4().hex[:8]}")
    tenant_id: str
    name: str
    criteria: dict[str, Any] = Field(default_factory=dict)
    size: int = 0
    avg_churn_risk: float = 0.0
    avg_qoe_score: float = 0.0


class ChurnRiskResult(BaseModel):
    tenant_id: str
    segment_id: str
    churn_risk: float
    factors: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""


class GrowthInsight(BaseModel):
    insight_id: str = Field(default_factory=lambda: f"INS-{uuid4().hex[:8]}")
    tenant_id: str
    category: str  # retention, growth, engagement
    title: str
    description: str = ""
    impact_score: float = 0.0
    suggested_action: str = ""


class NLQueryResult(BaseModel):
    query: str
    generated_sql: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: int = 0


class RetentionCampaign(BaseModel):
    campaign_id: str = Field(default_factory=lambda: f"CMP-{uuid4().hex[:8]}")
    tenant_id: str
    segment_id: str
    campaign_type: str  # email, push, in_app
    message: str = ""
    status: str = "pending"  # pending, approved, sent, cancelled
