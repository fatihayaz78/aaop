"""AgentDecision schema written to DuckDB shared_analytics.agent_decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.schemas.base_event import RiskLevel


class AgentDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    app: str
    action: str
    risk_level: RiskLevel
    approval_required: bool = False
    llm_model_used: str
    reasoning_summary: str | None = None
    tools_executed: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    duration_ms: int | None = None
    input_event_id: str | None = None
    output_event_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
