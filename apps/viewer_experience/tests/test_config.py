"""Tests for Viewer Experience config."""

from __future__ import annotations

from apps.viewer_experience.config import ViewerExperienceConfig


def test_defaults():
    cfg = ViewerExperienceConfig()
    assert cfg.qoe_degradation_threshold == 2.5
    assert cfg.session_dedup_window_seconds == 300


def test_custom():
    cfg = ViewerExperienceConfig(qoe_degradation_threshold=3.0, session_dedup_window_seconds=600)
    assert cfg.qoe_degradation_threshold == 3.0
