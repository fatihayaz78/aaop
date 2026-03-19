"""Tests for Live Intelligence schemas."""

from __future__ import annotations

from apps.live_intelligence.schemas import (
    DRMStatus,
    EPGEntry,
    ExternalConnector,
    LiveEvent,
    ScaleRecommendation,
    SportRadarData,
)


def test_live_event_defaults():
    e = LiveEvent(tenant_id="t1", event_name="Match")
    assert e.event_id.startswith("EVT-")
    assert e.status == "scheduled"
    assert e.pre_scale_done is False


def test_drm_status_all_healthy():
    d = DRMStatus(tenant_id="t1")
    assert d.all_healthy is True


def test_drm_status_degraded():
    d = DRMStatus(tenant_id="t1", widevine="down", fairplay="healthy", playready="degraded")
    assert d.all_healthy is False
    assert d.widevine == "down"
    assert d.playready == "degraded"


def test_sportradar_data():
    s = SportRadarData(match_id="m1", tenant_id="t1", home_team="GS", away_team="FB")
    assert s.status == "not_started"
    assert s.minute == 0


def test_epg_entry():
    e = EPGEntry(tenant_id="t1", title="Movie Night", channel="CH1")
    assert e.content_type == ""


def test_external_connector():
    c = ExternalConnector(tenant_id="t1", connector="sportradar", poll_seconds=30)
    assert c.is_active is True
    assert c.status == "idle"


def test_scale_recommendation():
    r = ScaleRecommendation(event_id="e1", tenant_id="t1", scale_factor=2.0, expected_viewers=200_000)
    assert r.reason == ""
