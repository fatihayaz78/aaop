"""Tests for Ops Center config."""

from __future__ import annotations

from apps.ops_center.config import OpsCenterConfig


def test_defaults():
    cfg = OpsCenterConfig()
    assert cfg.p1_mttr_target_seconds == 300
    assert cfg.auto_rca_severities == ["P0", "P1"]
    assert cfg.fp_rate_threshold == 0.15
    assert cfg.fp_rate_window_days == 7


def test_custom_values():
    cfg = OpsCenterConfig(p1_mttr_target_seconds=600, fp_rate_threshold=0.10)
    assert cfg.p1_mttr_target_seconds == 600
    assert cfg.fp_rate_threshold == 0.10
