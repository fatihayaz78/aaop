"""Tests for Live Intelligence tools."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.live_intelligence.schemas import DRMStatus, LiveEvent, ScaleRecommendation, SportRadarData
from apps.live_intelligence.tools import (
    cache_active_event,
    cache_drm_status,
    cache_sportradar,
    calculate_scale_factor,
    get_drm_status,
    get_sportradar_data,
    override_drm_fallback,
    publish_event_start,
    publish_external_update,
    trigger_pre_scale,
)
from shared.event_bus import EventBus, EventType

# ── Scale factor calculation ──


@pytest.mark.asyncio
async def test_scale_high_viewers():
    event = LiveEvent(tenant_id="t1", event_name="Derby", expected_viewers=600_000)
    rec = await calculate_scale_factor("t1", event)
    assert rec.scale_factor == 3.0


@pytest.mark.asyncio
async def test_scale_medium_viewers():
    event = LiveEvent(tenant_id="t1", event_name="Match", expected_viewers=200_000)
    rec = await calculate_scale_factor("t1", event)
    assert rec.scale_factor == 2.0


@pytest.mark.asyncio
async def test_scale_low_viewers():
    event = LiveEvent(tenant_id="t1", event_name="Show", expected_viewers=60_000)
    rec = await calculate_scale_factor("t1", event)
    assert rec.scale_factor == 1.5


@pytest.mark.asyncio
async def test_scale_minimal_viewers():
    event = LiveEvent(tenant_id="t1", event_name="Rerun", expected_viewers=10_000)
    rec = await calculate_scale_factor("t1", event)
    assert rec.scale_factor == 1.0


# ── DRM status ──


@pytest.mark.asyncio
async def test_get_drm_default(mock_redis: MagicMock):
    drm = await get_drm_status("t1", mock_redis)
    assert drm.widevine == "healthy"
    assert drm.fairplay == "healthy"
    assert drm.playready == "healthy"
    assert drm.all_healthy is True


@pytest.mark.asyncio
async def test_get_drm_cached(mock_redis: MagicMock):
    mock_redis.get_json = AsyncMock(return_value={
        "tenant_id": "t1", "widevine": "down", "fairplay": "healthy", "playready": "degraded",
    })
    drm = await get_drm_status("t1", mock_redis)
    assert drm.widevine == "down"
    assert drm.playready == "degraded"
    assert drm.all_healthy is False


# ── SportRadar cache ──


@pytest.mark.asyncio
async def test_get_sportradar_miss(mock_redis: MagicMock):
    result = await get_sportradar_data("t1", "match-123", mock_redis)
    assert result is None


@pytest.mark.asyncio
async def test_get_sportradar_hit(mock_redis: MagicMock):
    mock_redis.get_json = AsyncMock(return_value={
        "match_id": "m1", "tenant_id": "t1", "home_team": "GS", "away_team": "FB",
        "score": "2-1", "status": "live", "minute": 65,
    })
    result = await get_sportradar_data("t1", "m1", mock_redis)
    assert result is not None
    assert result.home_team == "GS"
    assert result.status == "live"


# ── Redis TTL tests ──


@pytest.mark.asyncio
async def test_cache_drm_ttl(mock_redis: MagicMock):
    drm = DRMStatus(tenant_id="t1")
    await cache_drm_status("t1", drm, mock_redis)
    call = mock_redis.set_json.call_args
    assert call.kwargs.get("ttl") == 60  # drm_status_ttl


@pytest.mark.asyncio
async def test_cache_sportradar_ttl(mock_redis: MagicMock):
    data = SportRadarData(match_id="m1", tenant_id="t1")
    await cache_sportradar("t1", "m1", data, mock_redis)
    call = mock_redis.set_json.call_args
    assert call.kwargs.get("ttl") == 30  # sportradar_ttl


@pytest.mark.asyncio
async def test_cache_active_event_ttl(mock_redis: MagicMock):
    event = LiveEvent(tenant_id="t1", event_name="Match")
    await cache_active_event("t1", event, mock_redis)
    call = mock_redis.set_json.call_args
    assert call.kwargs.get("ttl") == 60  # active_event_ttl


# ── HIGH risk tools ──


@pytest.mark.asyncio
async def test_trigger_pre_scale_approval():
    rec = ScaleRecommendation(event_id="e1", tenant_id="t1", scale_factor=2.5, reason="High viewers")
    result = await trigger_pre_scale("t1", rec)
    assert result["status"] == "approval_required"
    assert result["scale_factor"] == 2.5


@pytest.mark.asyncio
async def test_override_drm_fallback_approval():
    result = await override_drm_fallback("t1", "widevine", "disable_drm")
    assert result["status"] == "approval_required"
    assert result["provider"] == "widevine"


# ── Event publishing ──


@pytest.mark.asyncio
async def test_publish_event_start(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.LIVE_EVENT_STARTING, handler)
    await event_bus.start()

    event = LiveEvent(
        tenant_id="t1", event_name="GS vs FB",
        kickoff_time=datetime(2026, 3, 20, 20, 0, tzinfo=UTC),
        expected_viewers=500_000,
    )
    await publish_event_start("t1", event, event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].payload["event_name"] == "GS vs FB"


@pytest.mark.asyncio
async def test_publish_external_update(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.EXTERNAL_DATA_UPDATED, handler)
    await event_bus.start()

    await publish_external_update("t1", "sportradar", {"score": "1-0"}, event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].payload["connector"] == "sportradar"
