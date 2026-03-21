"""Tests for Admin & Governance config."""

from __future__ import annotations

from apps.admin_governance.config import AdminGovernanceConfig


def test_defaults():
    cfg = AdminGovernanceConfig()
    assert cfg.api_key_mask_prefix == "sk-ant-..."
    assert cfg.api_key_mask_suffix_len == 4
    assert cfg.audit_log_retention_days == 365
    assert cfg.compliance_check_interval_hours == 168
    assert cfg.max_export_rows == 50_000
    assert cfg.required_role == "admin"


def test_custom():
    cfg = AdminGovernanceConfig(required_role="superadmin", max_export_rows=10_000)
    assert cfg.required_role == "superadmin"
    assert cfg.max_export_rows == 10_000
