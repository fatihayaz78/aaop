"""Router tests for Alert Center — 18 tests using FastAPI TestClient with mocked deps."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_duckdb, get_sqlite, get_tenant_context
from backend.main import app
from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext

# ── Mock factories ──

HEADERS = {"X-Tenant-ID": "s_sport_plus"}

MOCK_ALERT = {
    "alert_id": "ALT-test001", "tenant_id": "s_sport_plus", "source_app": "log_analyzer",
    "severity": "P0", "title": "CDN Anomaly", "channel": "slack", "status": "sent",
    "sent_at": "2026-03-25T10:00:00+00:00",
}


def _make_mock_duck(*, alerts: list | None = None, empty: bool = False) -> DuckDBClient:
    mock = MagicMock(spec=DuckDBClient)
    _alerts = [] if empty else (alerts or [MOCK_ALERT])

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "count" in sql_l:
            if "status = 'sent'" in sql_l:
                return {"cnt": sum(1 for a in _alerts if a.get("status") == "sent")}
            return {"cnt": len(_alerts)}
        return None

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        if "group by severity" in sql_l:
            from collections import Counter
            c = Counter(a["severity"] for a in _alerts)
            return [{"severity": k, "cnt": v} for k, v in c.items()]
        if "group by channel" in sql_l:
            from collections import Counter
            c = Counter(a.get("channel", "slack") for a in _alerts)
            return [{"channel": k, "cnt": v} for k, v in c.items()]
        if "group by source_app" in sql_l:
            from collections import Counter
            c = Counter(a.get("source_app", "") for a in _alerts)
            return [{"source_app": k, "cnt": v} for k, v in c.items()][:5]
        if "extract(hour" in sql_l:
            return [{"hr": h, "cnt": 1} for h in range(24)]
        if "cast(sent_at" in sql_l:
            return [{"day": "2026-03-25", "cnt": len(_alerts)}]
        if "alerts_sent" in sql_l:
            result = list(_alerts)
            if params:
                for p in params:
                    if isinstance(p, str) and p in ("P0", "P1", "P2", "P3"):
                        result = [a for a in result if a["severity"] == p]
            return result
        return []

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    mock.execute.return_value = None
    return mock


@pytest.fixture
async def mock_sqlite(tmp_path):
    """Real in-memory SQLite for alert_center tables."""
    db_path = str(tmp_path / "test_alert.db")
    client = SQLiteClient(db_path=db_path)
    await client.connect()
    # Create tables
    await client.execute("""CREATE TABLE IF NOT EXISTS alert_rules (
        id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT, event_types TEXT,
        severity_min TEXT, channels TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    )""")
    await client.execute("""CREATE TABLE IF NOT EXISTS alert_channels (
        id TEXT PRIMARY KEY, tenant_id TEXT, channel_type TEXT, name TEXT,
        config_json TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    )""")
    await client.execute("""CREATE TABLE IF NOT EXISTS suppression_rules (
        id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT, start_time TEXT,
        end_time TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    )""")
    # Seed data
    await client.execute(
        "INSERT INTO alert_rules (id, tenant_id, name, event_types, severity_min, channels) VALUES (?,?,?,?,?,?)",
        ("rule-test1", "s_sport_plus", "CDN Alert", '["cdn_anomaly_detected"]', "P1", '["slack"]'),
    )
    await client.execute(
        "INSERT INTO alert_channels (id, tenant_id, channel_type, name, config_json) VALUES (?,?,?,?,?)",
        ("ch-test1", "s_sport_plus", "slack", "NOC Slack", '{"webhook":"https://..."}'),
    )
    await client.execute(
        "INSERT INTO suppression_rules (id, tenant_id, name, start_time, end_time) VALUES (?,?,?,?,?)",
        ("sup-test1", "s_sport_plus", "Maint Window", "2026-03-26T02:00", "2026-03-26T04:00"),
    )
    yield client
    await client.disconnect()


@pytest.fixture
def client(mock_sqlite):
    """TestClient with mocked DuckDB + real SQLite."""
    import backend.routers.alert_center as ac
    ac._schema_ready = True  # Skip schema init since we already created tables

    mock_duck = _make_mock_duck()

    app.dependency_overrides[get_duckdb] = lambda: mock_duck
    app.dependency_overrides[get_sqlite] = lambda: mock_sqlite
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ══════════ Dashboard ══════════

def test_dashboard_returns_expected_shape(client: TestClient):
    res = client.get("/alerts/dashboard", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    for key in ("total_alerts_24h", "active_alerts", "dedup_hit_rate", "storm_events_7d", "severity_breakdown", "channel_breakdown", "alert_trend_24h"):
        assert key in data, f"Missing key: {key}"


def test_dashboard_trend_has_24_slots(client: TestClient):
    res = client.get("/alerts/dashboard", headers=HEADERS)
    data = res.json()
    assert len(data["alert_trend_24h"]) == 24


# ══════════ Alert List ══════════

def test_alerts_list_returns_paginated(client: TestClient):
    res = client.get("/alerts/list", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data


def test_alerts_filter_by_severity(client: TestClient):
    res = client.get("/alerts/list?severity=P0", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["severity"] == "P0"


# ══════════ Rules CRUD ══════════

def test_rules_list_returns_seeded_rules(client: TestClient):
    res = client.get("/alerts/rules", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1


def test_rules_create_valid(client: TestClient):
    res = client.post("/alerts/rules", json={
        "name": "Test Rule", "event_types": ["incident_created"],
        "severity_min": "P2", "channels": ["slack"],
    }, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data


def test_rules_create_missing_field_422(client: TestClient):
    res = client.post("/alerts/rules", json={"event_types": ["x"]}, headers=HEADERS)
    assert res.status_code == 422


def test_rules_patch_active_toggle(client: TestClient):
    res = client.patch("/alerts/rules/rule-test1", json={"is_active": 0}, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "updated"


def test_rules_delete_soft(client: TestClient):
    # Create then delete
    create_res = client.post("/alerts/rules", json={
        "name": "ToDelete", "event_types": ["x"], "channels": ["email"],
    }, headers=HEADERS)
    rule_id = create_res.json()["id"]
    res = client.delete(f"/alerts/rules/{rule_id}", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["deleted"] is True


# ══════════ Channels ══════════

def test_channels_list_returns_items(client: TestClient):
    res = client.get("/alerts/channels", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1


# ══════════ Suppression ══════════

def test_suppression_list_returns_items(client: TestClient):
    res = client.get("/alerts/suppression", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1


def test_suppression_create_valid(client: TestClient):
    res = client.post("/alerts/suppression", json={
        "name": "Deploy Window", "start_time": "2026-04-01T01:00", "end_time": "2026-04-01T02:00",
    }, headers=HEADERS)
    assert res.status_code == 200
    assert "id" in res.json()


# ══════════ Analytics ══════════

def test_analytics_returns_expected_shape(client: TestClient):
    res = client.get("/alerts/analytics", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    for key in ("mtta_p50_seconds", "top_event_types", "channel_performance", "daily_volume_7d"):
        assert key in data


def test_analytics_top_event_types_max_5(client: TestClient):
    res = client.get("/alerts/analytics", headers=HEADERS)
    data = res.json()
    assert len(data["top_event_types"]) <= 5


# ══════════ Auth ══════════

def test_dashboard_requires_auth():
    app.dependency_overrides.clear()
    import backend.routers.alert_center as ac
    import inspect
    sig = inspect.signature(ac.dashboard)
    assert "ctx" in sig.parameters


def test_list_requires_auth():
    import backend.routers.alert_center as ac
    import inspect
    sig = inspect.signature(ac.list_alerts)
    assert "ctx" in sig.parameters


def test_rules_requires_auth():
    import backend.routers.alert_center as ac
    import inspect
    sig = inspect.signature(ac.list_rules)
    assert "ctx" in sig.parameters


def test_suppression_requires_auth():
    import backend.routers.alert_center as ac
    import inspect
    sig = inspect.signature(ac.list_suppression)
    assert "ctx" in sig.parameters
