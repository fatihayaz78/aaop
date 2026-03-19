"""Live Intelligence tools — all require tenant_id as first param. Risk-level tagged."""

from __future__ import annotations

from typing import Any

import structlog

from apps.live_intelligence.config import LiveIntelligenceConfig
from apps.live_intelligence.schemas import DRMStatus, EPGEntry, LiveEvent, ScaleRecommendation, SportRadarData
from shared.event_bus import EventType
from shared.schemas.base_event import BaseEvent, SeverityLevel

logger = structlog.get_logger(__name__)


# ── LOW risk tools ──────────────────────────────────────


async def get_upcoming_events(tenant_id: str, db: Any) -> list[dict]:
    """Get upcoming live events. Risk: LOW."""
    return db.fetch_all(
        "SELECT * FROM shared_analytics.live_events WHERE tenant_id = ? AND status = 'scheduled' ORDER BY kickoff_time",
        [tenant_id],
    )


async def get_sportradar_data(tenant_id: str, match_id: str, redis: Any) -> SportRadarData | None:
    """Get cached SportRadar data. Risk: LOW. Poll: 30s."""
    LiveIntelligenceConfig()
    key = f"ctx:{tenant_id}:sportradar:{match_id}"
    data = await redis.get_json(key)
    if data:
        return SportRadarData(**data)
    return None


async def get_drm_status(tenant_id: str, redis: Any) -> DRMStatus:
    """Get DRM status (Widevine, FairPlay, PlayReady). Risk: LOW. Poll: 60s."""
    key = f"ctx:{tenant_id}:drm:status"
    data = await redis.get_json(key)
    if data:
        return DRMStatus(**data)
    return DRMStatus(tenant_id=tenant_id)


async def get_epg_schedule(tenant_id: str) -> list[EPGEntry]:
    """Get EPG schedule. Risk: LOW. Poll: 300s."""
    logger.info("epg_schedule_fetched", tenant_id=tenant_id)
    return []


async def calculate_scale_factor(
    tenant_id: str, event: LiveEvent, historical_data: list[dict] | None = None,
) -> ScaleRecommendation:
    """Calculate pre-scale factor based on expected viewers. Risk: LOW."""
    base_factor = 1.0
    if event.expected_viewers > 500_000:
        base_factor = 3.0
    elif event.expected_viewers > 100_000:
        base_factor = 2.0
    elif event.expected_viewers > 50_000:
        base_factor = 1.5

    return ScaleRecommendation(
        event_id=event.event_id,
        tenant_id=tenant_id,
        scale_factor=base_factor,
        expected_viewers=event.expected_viewers,
        reason=f"Based on {event.expected_viewers:,} expected viewers",
    )


# ── MEDIUM risk tools ───────────────────────────────────


async def register_live_event(tenant_id: str, event: LiveEvent, db: Any) -> str:
    """Register live event in DuckDB. Risk: MEDIUM (auto+notify)."""
    db.execute(
        """INSERT INTO shared_analytics.live_events
        (event_id, tenant_id, event_name, sport, competition, kickoff_time,
         status, expected_viewers, sportradar_id, epg_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            event.event_id, tenant_id, event.event_name, event.sport,
            event.competition,
            event.kickoff_time.isoformat() if event.kickoff_time else None,
            event.status, event.expected_viewers, event.sportradar_id, event.epg_id,
        ],
    )
    logger.info("live_event_registered", tenant_id=tenant_id, event_id=event.event_id)
    return event.event_id


async def update_event_status(tenant_id: str, event_id: str, status: str, db: Any) -> None:
    """Update live event status. Risk: MEDIUM (auto+notify)."""
    db.execute(
        "UPDATE shared_analytics.live_events SET status = ? WHERE event_id = ? AND tenant_id = ?",
        [status, event_id, tenant_id],
    )
    logger.info("event_status_updated", tenant_id=tenant_id, event_id=event_id, status=status)


async def publish_event_start(tenant_id: str, event: LiveEvent, event_bus: Any) -> None:
    """Publish live_event_starting (30 min before kickoff). Risk: MEDIUM (auto+notify)."""
    bus_event = BaseEvent(
        event_type=EventType.LIVE_EVENT_STARTING,
        tenant_id=tenant_id,
        source_app="live_intelligence",
        severity=SeverityLevel.P2,
        payload={
            "event_id": event.event_id,
            "event_name": event.event_name,
            "kickoff_time": event.kickoff_time.isoformat() if event.kickoff_time else None,
            "expected_viewers": event.expected_viewers,
            "sport": event.sport,
            "competition": event.competition,
        },
    )
    await event_bus.publish(bus_event)
    logger.info("live_event_starting_published", tenant_id=tenant_id, event_id=event.event_id)


async def publish_external_update(
    tenant_id: str, connector: str, data: dict, event_bus: Any,
) -> None:
    """Publish external_data_updated event. Risk: MEDIUM (auto+notify)."""
    bus_event = BaseEvent(
        event_type=EventType.EXTERNAL_DATA_UPDATED,
        tenant_id=tenant_id,
        source_app="live_intelligence",
        severity=SeverityLevel.P3,
        payload={"connector": connector, "data": data},
    )
    await event_bus.publish(bus_event)
    logger.info("external_data_updated_published", tenant_id=tenant_id, connector=connector)


async def cache_drm_status(tenant_id: str, drm: DRMStatus, redis: Any) -> None:
    """Cache DRM status in Redis. TTL: 60s."""
    config = LiveIntelligenceConfig()
    key = f"ctx:{tenant_id}:drm:status"
    await redis.set_json(key, drm.model_dump(), ttl=config.drm_status_ttl)


async def cache_sportradar(tenant_id: str, match_id: str, data: SportRadarData, redis: Any) -> None:
    """Cache SportRadar data. TTL: 30s."""
    config = LiveIntelligenceConfig()
    key = f"ctx:{tenant_id}:sportradar:{match_id}"
    await redis.set_json(key, data.model_dump(), ttl=config.sportradar_ttl)


async def cache_active_event(tenant_id: str, event: LiveEvent, redis: Any) -> None:
    """Cache active event. TTL: 60s."""
    config = LiveIntelligenceConfig()
    key = f"ctx:{tenant_id}:live:active_event"
    await redis.set_json(key, event.model_dump(), ttl=config.active_event_ttl)


# ── HIGH risk tools ─────────────────────────────────────


async def trigger_pre_scale(tenant_id: str, recommendation: ScaleRecommendation) -> dict:
    """Trigger CDN pre-scaling. Risk: HIGH (approval_required)."""
    logger.warning(
        "pre_scale_requested", tenant_id=tenant_id,
        event_id=recommendation.event_id, factor=recommendation.scale_factor,
    )
    return {
        "status": "approval_required",
        "event_id": recommendation.event_id,
        "scale_factor": recommendation.scale_factor,
        "reason": recommendation.reason,
    }


async def override_drm_fallback(tenant_id: str, provider: str, fallback_action: str) -> dict:
    """Override DRM fallback. Risk: HIGH (approval_required)."""
    logger.warning(
        "drm_fallback_override_requested", tenant_id=tenant_id,
        provider=provider, fallback=fallback_action,
    )
    return {
        "status": "approval_required",
        "provider": provider,
        "fallback_action": fallback_action,
    }
