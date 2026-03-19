"""Viewer Experience Pydantic v2 models — QoE sessions, complaints."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class QoESession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    user_id_hash: str = ""
    content_id: str = ""
    device_type: str = ""
    region: str = ""
    buffering_ratio: float = 0.0
    startup_time_ms: int = 0
    bitrate_avg: int = 0
    quality_score: float = 0.0
    errors: list[str] = Field(default_factory=list)
    event_ts: datetime = Field(default_factory=datetime.utcnow)


class QoEAnomaly(BaseModel):
    session_id: str
    tenant_id: str
    quality_score: float
    reason: str
    severity: str = "P2"


class Complaint(BaseModel):
    id: str = Field(default_factory=lambda: f"CMP-{uuid4().hex[:12]}")
    tenant_id: str
    source: str = ""
    content: str = ""
    category: str = ""
    sentiment: str = ""
    priority: str = ""
    status: str = "open"
    content_hash: str = ""
    resolution: str | None = None
    related_session_id: str | None = None
    similar_complaint_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComplaintAnalysis(BaseModel):
    complaint_id: str
    category: str
    sentiment: str
    priority: str
    summary: str = ""
    similar_count: int = 0
