"""Tests for Live Intelligence config."""

from __future__ import annotations

from apps.live_intelligence.config import LiveIntelligenceConfig


def test_defaults():
    cfg = LiveIntelligenceConfig()
    assert cfg.pre_event_trigger_minutes == 30
    assert cfg.sportradar_poll_seconds == 30
    assert cfg.drm_poll_seconds == 60
    assert cfg.epg_poll_seconds == 300
    assert cfg.active_event_ttl == 60
    assert cfg.pre_scale_status_ttl == 3600
    assert cfg.drm_status_ttl == 60
    assert cfg.sportradar_ttl == 30


def test_custom():
    cfg = LiveIntelligenceConfig(sportradar_poll_seconds=15, drm_poll_seconds=30)
    assert cfg.sportradar_poll_seconds == 15
    assert cfg.drm_poll_seconds == 30
