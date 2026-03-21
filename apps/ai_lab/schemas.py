"""AI Lab Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Experiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"EXP-{uuid4().hex[:12]}")
    tenant_id: str
    name: str
    description: str = ""
    variants: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "draft"  # draft, running, completed, cancelled
    metric: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExperimentResult(BaseModel):
    experiment_id: str
    variant_id: str
    sample_size: int = 0
    metric_value: float = 0.0
    p_value: float | None = None
    confidence_interval: tuple[float, float] | None = None
    is_significant: bool = False


class ModelRegistryEntry(BaseModel):
    model_id: str = Field(default_factory=lambda: f"MDL-{uuid4().hex[:8]}")
    model_name: str
    version: str = "1.0"
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromptVersion(BaseModel):
    prompt_id: str = Field(default_factory=lambda: f"PRM-{uuid4().hex[:8]}")
    app: str
    prompt_type: str
    version: int = 1
    content: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMCostMetrics(BaseModel):
    tenant_id: str
    period: str = "daily"
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    budget_used_pct: float = 0.0
    model_breakdown: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ModelEvaluation(BaseModel):
    eval_id: str = Field(default_factory=lambda: f"EVAL-{uuid4().hex[:8]}")
    model_name: str
    tenant_id: str
    accuracy: float = 0.0
    latency_p50_ms: int = 0
    latency_p99_ms: int = 0
    cost_per_request: float = 0.0
    drift_detected: bool = False
