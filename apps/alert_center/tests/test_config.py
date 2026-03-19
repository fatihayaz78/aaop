"""Tests for Alert Center config."""

from __future__ import annotations

from apps.alert_center.config import AlertCenterConfig


def test_defaults():
    cfg = AlertCenterConfig()
    assert cfg.dedup_window_seconds == 900
    assert cfg.storm_threshold_count == 10
    assert cfg.storm_window_seconds == 300


def test_custom():
    cfg = AlertCenterConfig(dedup_window_seconds=600, storm_threshold_count=20)
    assert cfg.dedup_window_seconds == 600
    assert cfg.storm_threshold_count == 20
