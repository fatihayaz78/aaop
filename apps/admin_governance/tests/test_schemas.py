"""Tests for Admin & Governance schemas."""

from __future__ import annotations

from apps.admin_governance.schemas import (
    APIKeyInfo,
    AuditEntry,
    ComplianceReport,
    ModuleConfig,
    TenantInfo,
    UsageStats,
    encrypt_api_key,
    generate_api_key,
    mask_api_key,
)


def test_tenant_info():
    t = TenantInfo(tenant_id="bein_sports", name="beIN Sports", plan="enterprise")
    assert t.is_active is True
    assert t.timezone == "Europe/Istanbul"


def test_module_config():
    m = ModuleConfig(module_name="ops_center", tenant_id="t1", is_enabled=True)
    assert m.is_enabled is True


def test_api_key_info():
    k = APIKeyInfo(tenant_id="t1", key_name="anthropic", masked_key="sk-ant-...abcd")
    assert k.key_id.startswith("KEY-")
    assert k.masked_key == "sk-ant-...abcd"


def test_audit_entry():
    a = AuditEntry(tenant_id="t1", action="create_tenant", success=True)
    assert a.audit_id.startswith("AUD-")


def test_compliance_report():
    r = ComplianceReport(tenant_id="t1", total_decisions=100, high_risk_decisions=5, approval_rate=95.0)
    assert r.report_id.startswith("CMP-")


def test_usage_stats():
    u = UsageStats(tenant_id="t1", total_agent_calls=500, model_usage={"sonnet": 300, "haiku": 200})
    assert u.total_agent_calls == 500


def test_mask_api_key():
    masked = mask_api_key("sk-ant-abcdefghijklmnop")
    assert masked == "sk-ant-...mnop"
    assert "abcdefgh" not in masked


def test_mask_api_key_short():
    masked = mask_api_key("short")
    assert masked == "sk-ant-...****"


def test_encrypt_api_key():
    encrypted = encrypt_api_key("sk-ant-test", "jwt-secret")
    assert len(encrypted) == 64  # SHA256 hex


def test_generate_api_key():
    key = generate_api_key()
    assert key.startswith("sk-ant-")
    assert len(key) > 20
