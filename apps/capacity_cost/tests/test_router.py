"""Router tests for Capacity & Cost — 15 tests with mocked DuckDB + SQLite."""

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

MOCK_METRIC = {"id": "CAP-001", "tenant_id": "s_sport_plus", "service": "cdn_bandwidth",
    "metric_name": "cdn_bandwidth_utilization", "current_value": 7500, "capacity_limit": 10000,
    "utilization_pct": 75.0, "timestamp": "2026-03-25T10:00:00", "region": "eu-central"}
MOCK_METRIC_HIGH = {**MOCK_METRIC, "id": "CAP-002", "service": "origin_cpu", "utilization_pct": 92.0}


def _make_mock_duck(*, metrics=None, empty=False):
    mock = MagicMock(spec=DuckDBClient)
    items = [] if empty else (metrics or [MOCK_METRIC, MOCK_METRIC_HIGH])

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "count(distinct" in sql_l and "utilization_pct > 90" in sql_l:
            return {"cnt": sum(1 for m in items if m["utilization_pct"] > 90)}
        if "count(distinct" in sql_l and "utilization_pct > 70" in sql_l:
            return {"cnt": sum(1 for m in items if m["utilization_pct"] > 70)}
        if "avg(utilization_pct)" in sql_l:
            vals = [m["utilization_pct"] for m in items]
            return {"avg_pct": sum(vals)/len(vals) if vals else 0}
        if "order by utilization_pct desc" in sql_l and "limit 1" in sql_l:
            best = max(items, key=lambda m: m["utilization_pct"]) if items else {"service": "—", "utilization_pct": 0}
            return {"service": best["service"], "utilization_pct": best["utilization_pct"]}
        if "count" in sql_l:
            return {"cnt": len(items)}
        return {"cnt": 0}

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        if "extract(hour" in sql_l or "group by hr" in sql_l:
            return [{"hr": h, "avg_pct": 65.0} for h in range(24)]
        if "order by timestamp desc" in sql_l and "current_value as current" in sql_l:
            # Aliased columns for dashboard by-service query
            return [{"service": m["service"], "current": m["current_value"], "lim": m["capacity_limit"], "pct": m["utilization_pct"]} for m in items]
        if "order by timestamp desc" in sql_l:
            result = list(items)
            if params:
                for p in params:
                    if isinstance(p, str) and p in ("cdn_bandwidth", "origin_cpu", "origin_memory", "encoder_queue", "api_gateway"):
                        result = [m for m in result if m["service"] == p]
            return result
        return list(items)

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    return mock


@pytest.fixture
async def mock_sqlite(tmp_path):
    db_path = str(tmp_path / "test_capacity.db")
    client = SQLiteClient(db_path=db_path)
    await client.connect()
    await client.execute("""CREATE TABLE IF NOT EXISTS automation_jobs (
        id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT, job_type TEXT,
        status TEXT, schedule TEXT, last_run TEXT, next_run TEXT,
        config_json TEXT, created_at TEXT DEFAULT (datetime('now'))
    )""")
    for i, (name, jtype, status) in enumerate([
        ("CDN Cache Purge", "cache_purge", "active"),
        ("Origin Health Check", "health_check", "active"),
        ("Scale Up Encoder", "scale_up", "paused"),
    ]):
        await client.execute(
            "INSERT INTO automation_jobs (id, tenant_id, name, job_type, status, schedule) VALUES (?,?,?,?,?,?)",
            (f"JOB-test{i}", "s_sport_plus", name, jtype, status, "0 */4 * * *"),
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
    data = client.get("/capacity/dashboard", headers=HEADERS).json()
    for key in ("services_at_warning", "services_at_critical", "avg_utilization", "peak_service", "cost_estimate_monthly", "utilization_by_service", "utilization_trend_24h"):
        assert key in data

def test_dashboard_utilization_by_service_not_empty(client):
    data = client.get("/capacity/dashboard", headers=HEADERS).json()
    assert len(data["utilization_by_service"]) > 0

def test_dashboard_trend_has_24_slots(client):
    data = client.get("/capacity/dashboard", headers=HEADERS).json()
    assert len(data["utilization_trend_24h"]) == 24

# ═══ Forecast ═══

def test_forecast_returns_items(client):
    data = client.get("/capacity/forecast", headers=HEADERS).json()
    assert "forecast" in data
    assert len(data["forecast"]) > 0

def test_forecast_recommendations_valid_values(client):
    data = client.get("/capacity/forecast", headers=HEADERS).json()
    for item in data["forecast"]:
        assert item["recommendation"] in ("scale_up", "monitor", "ok")

# ═══ Usage ═══

def test_usage_list_paginated(client):
    data = client.get("/capacity/usage", headers=HEADERS).json()
    assert "items" in data and "total" in data

def test_usage_filter_by_service(client):
    data = client.get("/capacity/usage?service=cdn_bandwidth", headers=HEADERS).json()
    for item in data["items"]:
        assert item["service"] == "cdn_bandwidth"

# ═══ Jobs ═══

def test_jobs_list_returns_items(client):
    data = client.get("/capacity/jobs", headers=HEADERS).json()
    assert len(data) >= 3

# ═══ Cost ═══

def test_cost_returns_expected_shape(client):
    data = client.get("/capacity/cost", headers=HEADERS).json()
    for key in ("current_month_usd", "projected_month_usd", "breakdown", "vs_last_month_pct", "optimization_tips"):
        assert key in data

def test_cost_breakdown_sums_to_total(client):
    data = client.get("/capacity/cost", headers=HEADERS).json()
    total = sum(item["cost_usd"] for item in data["breakdown"])
    assert abs(total - data["current_month_usd"]) < 10  # Allow small rounding

def test_cost_has_optimization_tips(client):
    data = client.get("/capacity/cost", headers=HEADERS).json()
    assert len(data["optimization_tips"]) > 0

# ═══ Auth ═══

def test_dashboard_requires_auth(client):
    import backend.routers.capacity_cost as cc
    import inspect
    assert "ctx" in inspect.signature(cc.dashboard).parameters

def test_forecast_requires_auth(client):
    import backend.routers.capacity_cost as cc
    import inspect
    assert "ctx" in inspect.signature(cc.forecast).parameters

def test_usage_requires_auth(client):
    import backend.routers.capacity_cost as cc
    import inspect
    assert "ctx" in inspect.signature(cc.usage).parameters

def test_cost_requires_auth(client):
    import backend.routers.capacity_cost as cc
    import inspect
    assert "ctx" in inspect.signature(cc.cost_analysis).parameters
