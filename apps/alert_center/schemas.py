"""Alert Center Pydantic v2 models."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.schemas.base_event import SeverityLevel


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: f"ALT-{uuid4().hex[:12]}")
    tenant_id: str
    source_app: str
    event_type: str
    severity: SeverityLevel
    title: str
    message: str = ""
    channels_routed: list[str] = Field(default_factory=list)
    status: str = "sent"
    decision_id: str | None = None
    fingerprint: str = ""
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    acked_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlertRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    name: str
    event_types: list[str] = Field(default_factory=list)
    severity_min: SeverityLevel = SeverityLevel.P3
    channels: list[str] = Field(default_factory=list)
    is_active: bool = True


class AlertChannel(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    channel_type: str  # slack, pagerduty, email
    name: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class SuppressionRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    name: str
    start_time: datetime
    end_time: datetime
    is_active: bool = True


class RoutingDecision(BaseModel):
    alert: Alert
    action: str  # "route", "dedup_drop", "suppress_drop", "storm_summary"
    channels: list[str] = Field(default_factory=list)
    approval_required: bool = False
    reason: str = ""


def compute_fingerprint(tenant_id: str, source_app: str, event_type: str, severity: str) -> str:
    """Deterministic fingerprint for dedup."""
    raw = f"{tenant_id}:{source_app}:{event_type}:{severity}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
