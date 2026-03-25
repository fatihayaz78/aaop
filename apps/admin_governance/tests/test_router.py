"""Router tests for Admin & Governance — 18 tests with mocked DuckDB + real SQLite."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from backend.main import app
from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext

HEADERS = {"X-Tenant-ID": "s_sport_plus"}


def _make_mock_duck():
    mock = MagicMock(spec=DuckDBClient)

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "sum(cost_usd) as total_cost" in sql_l:
            return {"total_cost": 8.50, "inp": 120000, "outp": 60000}
        if "sum(input_tokens)" in sql_l:
            return {"inp": 50000, "outp": 25000, "cost": 1.25}
        return {"cnt": 5}

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        if "group by model" in sql_l:
            return [
                {"model": "claude-haiku-4-5-20251001", "calls": 100, "cost": 0.50},
                {"model": "claude-sonnet-4-20250514", "calls": 60, "cost": 3.00},
                {"model": "claude-opus-4-20250514", "calls": 20, "cost": 5.00},
            ]
        if "group by app_name" in sql_l:
            return [
                {"app": "ops_center", "calls": 50, "cost": 2.50},
                {"app": "log_analyzer", "calls": 80, "cost": 3.00},
            ]
        if "cast(created_at" in sql_l or "group by day" in sql_l:
            return [{"day": "2026-03-25", "cost": 1.20}]
        return []

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    mock.execute.return_value = None
    return mock


@pytest.fixture
async def mock_sqlite(tmp_path):
    db_path = str(tmp_path / "test_admin.db")
    client = SQLiteClient(db_path=db_path)
    await client.connect()
    await client.init_tables()
    # Add status column to audit_log (built-in table lacks it)
    try:
        await client.execute("ALTER TABLE audit_log ADD COLUMN status TEXT DEFAULT 'success'")
    except Exception:
        pass
    try:
        await client.execute("ALTER TABLE audit_log ADD COLUMN resource_id TEXT")
    except Exception:
        pass
    # Seed tenants
    await client.execute("INSERT OR IGNORE INTO tenants (id, name, plan, is_active) VALUES (?,?,?,1)", ("t1", "Test Tenant", "enterprise"))
    await client.execute("INSERT OR IGNORE INTO tenants (id, name, plan, is_active) VALUES (?,?,?,1)", ("t2", "Second", "pro"))
    # Seed module configs
    await client.execute("INSERT OR IGNORE INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)", ("mc1", "t1", "ops_center", 1))
    await client.execute("INSERT OR IGNORE INTO module_configs (id, tenant_id, module_name, is_enabled) VALUES (?,?,?,?)", ("mc2", "t1", "log_analyzer", 0))
    # Seed audit_log
    await client.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id TEXT PRIMARY KEY, tenant_id TEXT, user_id TEXT, action TEXT,
        resource TEXT, resource_id TEXT, status TEXT, ip_hash TEXT, created_at TEXT
    )""")
    for i in range(10):
        status = "failed" if i < 2 else "success"
        tid = "t1" if i < 7 else "t2"
        await client.execute(
            "INSERT INTO audit_log (id, tenant_id, user_id, action, resource, status, ip_hash, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"AUD-{i}", tid, f"user-{i}", "login" if i % 2 == 0 else "view_dashboard", "auth", status, "abc", "2026-03-25T10:00:00"),
        )
    yield client
    await client.disconnect()


@pytest.fixture
def client(mock_sqlite):
    mock_duck = _make_mock_duck()
    app.dependency_overrides[get_duckdb] = lambda: mock_duck
    app.dependency_overrides[get_sqlite] = lambda: mock_sqlite
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ═══ Dashboard ═══

def test_dashboard_returns_expected_shape(client):
    data = client.get("/admin/dashboard", headers=HEADERS).json()
    for key in ("total_tenants", "active_tenants", "total_users", "audit_events_24h", "failed_actions_24h", "token_usage_today", "compliance_score", "top_actions"):
        assert key in data

def test_dashboard_has_token_usage_today(client):
    data = client.get("/admin/dashboard", headers=HEADERS).json()
    tu = data["token_usage_today"]
    for key in ("input", "output", "cost_usd"):
        assert key in tu

def test_dashboard_top_actions_max_5(client):
    data = client.get("/admin/dashboard", headers=HEADERS).json()
    assert len(data["top_actions"]) <= 5

# ═══ Tenants ═══

def test_tenants_list_returns_items(client):
    data = client.get("/admin/tenants", headers=HEADERS).json()
    assert len(data) >= 2

def test_tenants_create_valid(client):
    res = client.post("/admin/tenants", json={"name": "New Corp", "plan": "starter"}, headers=HEADERS)
    assert res.status_code == 200
    assert "id" in res.json()

def test_tenants_create_missing_name_422(client):
    res = client.post("/admin/tenants", json={"plan": "starter"}, headers=HEADERS)
    assert res.status_code == 422

# ═══ Modules ═══

def test_tenant_modules_get(client):
    data = client.get("/admin/tenants/t1/modules", headers=HEADERS).json()
    assert len(data) >= 1

def test_tenant_modules_patch_valid(client):
    res = client.patch("/admin/tenants/t1/modules", json={"app_name": "log_analyzer", "enabled": True}, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "updated"

# ═══ Audit ═══

def test_audit_list_paginated(client):
    data = client.get("/admin/audit", headers=HEADERS).json()
    assert "items" in data and "total" in data

def test_audit_filter_by_status_failed(client):
    data = client.get("/admin/audit?status=failed", headers=HEADERS).json()
    for item in data["items"]:
        assert item["status"] == "failed"

def test_audit_filter_by_tenant(client):
    data = client.get("/admin/audit?tenant_id=t1", headers=HEADERS).json()
    for item in data["items"]:
        assert item["tenant_id"] == "t1"

# ═══ Compliance ═══

def test_compliance_returns_checks(client):
    data = client.get("/admin/compliance", headers=HEADERS).json()
    assert "checks" in data
    assert len(data["checks"]) > 0

def test_compliance_checks_have_valid_status(client):
    data = client.get("/admin/compliance", headers=HEADERS).json()
    for check in data["checks"]:
        assert check["status"] in ("pass", "fail", "warning")

def test_compliance_has_overall_score(client):
    data = client.get("/admin/compliance", headers=HEADERS).json()
    assert "overall_score" in data
    assert isinstance(data["overall_score"], (int, float))

# ═══ Usage ═══

def test_usage_returns_expected_shape(client):
    data = client.get("/admin/usage", headers=HEADERS).json()
    for key in ("total_cost_7d", "cost_by_model", "cost_by_app", "daily_cost_7d", "token_breakdown"):
        assert key in data

def test_usage_cost_by_model_not_empty(client):
    data = client.get("/admin/usage", headers=HEADERS).json()
    assert len(data["cost_by_model"]) > 0

# ═══ Auth ═══

def test_dashboard_requires_auth(client):
    import backend.routers.admin_governance as ag
    import inspect
    assert "ctx" in inspect.signature(ag.dashboard).parameters

def test_audit_requires_auth(client):
    import backend.routers.admin_governance as ag
    import inspect
    assert "ctx" in inspect.signature(ag.audit_log).parameters
