"""Tests for Admin & Governance tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.admin_governance.tools import (
    create_tenant,
    delete_tenant,
    export_audit_log,
    generate_compliance_report,
    get_audit_log,
    get_module_configs,
    get_usage_stats,
    list_tenants,
    rotate_api_key,
    update_module_config,
)

# ── LOW risk ──


@pytest.mark.asyncio
async def test_list_tenants(mock_sqlite: MagicMock):
    mock_sqlite.fetch_all = MagicMock(return_value=[
        {"id": "t1", "name": "Test", "plan": "starter", "timezone": "UTC"},
    ])
    result = await list_tenants(mock_sqlite)
    assert len(result) == 1
    assert result[0].tenant_id == "t1"


@pytest.mark.asyncio
async def test_get_module_configs(mock_sqlite: MagicMock):
    mock_sqlite.fetch_all = MagicMock(return_value=[
        {"module_name": "ops_center", "is_enabled": 1},
    ])
    result = await get_module_configs("t1", mock_sqlite)
    assert len(result) == 1
    assert result[0].is_enabled is True


@pytest.mark.asyncio
async def test_get_audit_log(mock_sqlite: MagicMock):
    mock_sqlite.fetch_all = MagicMock(return_value=[{"action": "create_tenant"}])
    result = await get_audit_log("t1", mock_sqlite)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_usage_stats(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(side_effect=[
        [{"llm_model_used": "sonnet", "count": 100}],
        [{"count": 50}],
    ])
    result = await get_usage_stats("t1", mock_db)
    assert result.total_agent_calls == 100
    assert result.total_alerts == 50


@pytest.mark.asyncio
async def test_generate_compliance_report(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(side_effect=[
        [{"count": 200}],   # total
        [{"count": 10}],    # high_risk
        [{"count": 0}],     # unapproved
    ])
    report = await generate_compliance_report("t1", mock_db)
    assert report.total_decisions == 200
    assert report.high_risk_decisions == 10
    assert report.approval_rate == 95.0


@pytest.mark.asyncio
async def test_compliance_report_violations(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(side_effect=[
        [{"count": 100}],
        [{"count": 20}],
        [{"count": 5}],    # unapproved HIGH risk
    ])
    report = await generate_compliance_report("t1", mock_db)
    assert len(report.violations) == 1
    assert report.violations[0]["type"] == "unapproved_high_risk"


# ── MEDIUM risk ──


@pytest.mark.asyncio
async def test_create_tenant(mock_sqlite: MagicMock):
    result = await create_tenant("new_tenant", "New Co", "growth", mock_sqlite, "admin1")
    assert result.tenant_id == "new_tenant"
    assert result.plan == "growth"
    assert mock_sqlite.execute.call_count == 2  # INSERT tenant + audit


@pytest.mark.asyncio
async def test_update_module_config(mock_sqlite: MagicMock):
    result = await update_module_config("t1", "ops_center", False, mock_sqlite, "admin1")
    assert result.is_enabled is False
    assert mock_sqlite.execute.call_count == 2  # UPSERT + audit


# ── HIGH risk ──


@pytest.mark.asyncio
async def test_rotate_api_key(mock_sqlite: MagicMock):
    result = await rotate_api_key("t1", "anthropic", "jwt-secret-123", mock_sqlite, "admin1")
    assert result["status"] == "approval_required"
    assert result["masked_key"].startswith("sk-ant-...")
    assert len(result["masked_key"]) < 20  # masked, not full


@pytest.mark.asyncio
async def test_delete_tenant(mock_sqlite: MagicMock):
    result = await delete_tenant("t1", mock_sqlite, "admin1")
    assert result["status"] == "approval_required"
    assert result["tenant_id"] == "t1"


@pytest.mark.asyncio
async def test_export_audit_log(mock_sqlite: MagicMock):
    result = await export_audit_log("t1", mock_sqlite, "admin1")
    assert result["status"] == "approval_required"
    assert result["max_rows"] == 50_000


# ── Audit trail ──


@pytest.mark.asyncio
async def test_audit_written_on_create(mock_sqlite: MagicMock):
    """Every action must write to audit_log."""
    await create_tenant("t1", "Test", "starter", mock_sqlite)
    # Should have 2 execute calls: INSERT tenant + INSERT audit_log
    assert mock_sqlite.execute.call_count == 2


@pytest.mark.asyncio
async def test_audit_written_on_delete(mock_sqlite: MagicMock):
    await delete_tenant("t1", mock_sqlite, "admin1")
    # Should write audit even for approval_required
    assert mock_sqlite.execute.call_count >= 1


@pytest.mark.asyncio
async def test_audit_written_on_rotate(mock_sqlite: MagicMock):
    await rotate_api_key("t1", "key1", "secret", mock_sqlite, "admin1")
    assert mock_sqlite.execute.call_count >= 1
