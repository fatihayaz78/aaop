"""Base detector — abstract class for all anomaly detectors."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AnomalyEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    tenant_id: str
    detector: str
    severity: str  # P0, P1, P2
    metric: str
    current_value: float
    threshold: float
    window_minutes: int = 5
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_table: str = ""


class BaseDetector:
    name: str = "base"
    poll_interval_seconds: int = 30
    window_minutes: int = 5
    enabled: bool = True

    @abstractmethod
    async def check(self, tenant_id: str, schema: str) -> list[AnomalyEvent]:
        ...
