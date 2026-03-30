"""Real-time Anomaly API router — /realtime prefix."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_tenant_context
from shared.schemas.base_event import TenantContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/realtime", tags=["realtime"])


class DetectorToggle(BaseModel):
    enabled: bool


@router.get("/anomalies")
async def get_anomalies(
    ctx: TenantContext = Depends(get_tenant_context),
    minutes: int = Query(default=60),
) -> list[dict]:
    """Get recent anomalies from the engine's in-memory buffer."""
    from shared.realtime.anomaly_engine import get_anomaly_engine
    engine = get_anomaly_engine()
    events = engine.get_recent(minutes)
    return [e.model_dump() for e in events]


@router.get("/status")
async def get_status() -> dict:
    """Get engine status — running, detectors, last cycle."""
    from shared.realtime.anomaly_engine import get_anomaly_engine
    return get_anomaly_engine().get_status()


@router.post("/detectors/{name}/toggle")
async def toggle_detector(name: str, body: DetectorToggle) -> dict:
    """Enable/disable a specific detector."""
    from shared.realtime.anomaly_engine import get_anomaly_engine
    ok = get_anomaly_engine().toggle_detector(name, body.enabled)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Detector '{name}' not found")
    return {"name": name, "enabled": body.enabled}
