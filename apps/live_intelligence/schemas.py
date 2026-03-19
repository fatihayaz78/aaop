"""Live Intelligence Pydantic v2 models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class LiveEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid4().hex[:12]}")
    tenant_id: str
    event_name: str
    sport: str = ""
    competition: str = ""
    kickoff_time: datetime | None = None
    status: str = "scheduled"  # scheduled, live, completed
    expected_viewers: int = 0
    peak_viewers: int = 0
    pre_scale_done: bool = False
    sportradar_id: str | None = None
    epg_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DRMStatus(BaseModel):
    tenant_id: str
    widevine: str = "healthy"  # healthy, degraded, down
    fairplay: str = "healthy"
    playready: str = "healthy"
    checked_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def all_healthy(self) -> bool:
        return all(s == "healthy" for s in (self.widevine, self.fairplay, self.playready))


class SportRadarData(BaseModel):
    match_id: str
    tenant_id: str
    home_team: str = ""
    away_team: str = ""
    score: str = ""
    status: str = "not_started"  # not_started, live, finished
    minute: int = 0
    events: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EPGEntry(BaseModel):
    epg_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    tenant_id: str
    title: str
    channel: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    content_type: str = ""


class ExternalConnector(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tenant_id: str
    connector: str  # sportradar, drm, epg
    config_json: dict[str, Any] = Field(default_factory=dict)
    poll_seconds: int = 60
    is_active: bool = True
    last_synced: datetime | None = None
    status: str = "idle"


class ScaleRecommendation(BaseModel):
    event_id: str
    tenant_id: str
    scale_factor: float = 1.0
    reason: str = ""
    expected_viewers: int = 0
