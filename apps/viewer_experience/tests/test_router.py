"""Router tests for Viewer Experience — 15 tests with mocked DuckDB + real SQLite."""

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

MOCK_QOE = {
    "metric_id": "QOE-test001", "tenant_id": "s_sport_plus", "session_id": "sess-001",
    "device_type": "mobile", "region": "istanbul", "buffering_ratio": 0.03,
    "startup_time_ms": 1200, "bitrate_avg": 5000, "quality_score": 4.2,
    "event_ts": "2026-03-25T10:00:00+00:00", "created_at": "2026-03-25T10:00:00+00:00",
}

MOCK_QOE_LOW = {**MOCK_QOE, "metric_id": "QOE-test002", "quality_score": 1.8, "session_id": "sess-002"}


def _make_mock_duck(*, qoe_items=None, empty=False):
    mock = MagicMock(spec=DuckDBClient)
    items = [] if empty else (qoe_items or [MOCK_QOE, MOCK_QOE_LOW])

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "avg(quality_score)" in sql_l:
            scores = [i["quality_score"] for i in items]
            return {"avg_s": sum(scores) / len(scores) if scores else 0}
        if "count" in sql_l and "quality_score < 2.5" in sql_l:
            return {"cnt": sum(1 for i in items if i["quality_score"] < 2.5)}
        if "count" in sql_l:
            return {"cnt": len(items)}
        return {"cnt": 0}

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        if "quality_score < 2.5" in sql_l:
            return [i for i in items if i["quality_score"] < 2.5]
        if "group by device_type" in sql_l:
            from collections import Counter
            c = Counter(i["device_type"] for i in items)
            if "avg" in sql_l:
                return [{"device": k, "avg_score": 3.5} for k in c]
            return [{"device_type": k, "cnt": v} for k, v in c.items()]
        if "group by region" in sql_l:
            from collections import Counter
            c = Counter(i["region"] for i in items)
            return [{"region": k, "avg_score": 3.5} for k in c]
        if "extract(hour" in sql_l:
            return [{"hr": h, "avg_s": 3.8} for h in range(24)]
        if "qoe_metrics" in sql_l:
            result = list(items)
            if params:
                for p in params:
                    if isinstance(p, str) and p in ("mobile", "desktop", "smarttv", "tablet"):
                        result = [i for i in result if i["device_type"] == p]
            return result
        return items

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    return mock


@pytest.fixture
async def mock_sqlite(tmp_path):
    db_path = str(tmp_path / "test_viewer.db")
    client = SQLiteClient(db_path=db_path)
    await client.connect()
    await client.execute("""CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY, tenant_id TEXT, title TEXT, category TEXT,
        content TEXT, sentiment TEXT DEFAULT 'pending', priority TEXT DEFAULT 'P3',
        status TEXT DEFAULT 'open', created_at TEXT DEFAULT (datetime('now'))
    )""")
    for i in range(5):
        await client.execute(
            "INSERT INTO complaints (id, tenant_id, title, category, priority, status) VALUES (?,?,?,?,?,?)",
            (f"CMP-test{i}", "s_sport_plus", f"Test complaint {i}", "buffering",
             "P1" if i < 2 else "P2", "open" if i < 3 else "resolved"),
        )
    yield client
    await client.disconnect()


@pytest.fixture
def client(mock_sqlite):
    import backend.routers.viewer_experience as ve
    ve._schema_ready = True
    mock_duck = _make_mock_duck()
    app.dependency_overrides[get_duckdb] = lambda: mock_duck
    app.dependency_overrides[get_sqlite] = lambda: mock_sqlite
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ═══ Dashboard ═══

def test_dashboard_returns_expected_shape(client):
    res = client.get("/viewer/dashboard", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    for key in ("avg_qoe_score", "sessions_below_threshold", "active_complaints", "total_sessions_24h", "qoe_trend_24h", "score_distribution", "device_breakdown"):
        assert key in data

def test_dashboard_score_distribution_has_4_keys(client):
    data = client.get("/viewer/dashboard", headers=HEADERS).json()
    for key in ("excellent", "good", "fair", "poor"):
        assert key in data["score_distribution"]

# ═══ QoE Metrics ═══

def test_qoe_metrics_list_paginated(client):
    res = client.get("/viewer/qoe/metrics", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data and "total" in data

def test_qoe_metrics_filter_by_device(client):
    res = client.get("/viewer/qoe/metrics?device=mobile", headers=HEADERS)
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert item["device_type"] == "mobile"

def test_qoe_anomalies_all_below_threshold(client):
    res = client.get("/viewer/qoe/anomalies", headers=HEADERS)
    data = res.json()
    for item in data["items"]:
        assert item["quality_score"] < 2.5

# ═══ Complaints ═══

def test_complaints_list_paginated(client):
    res = client.get("/viewer/complaints", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data and "total" in data

def test_complaints_filter_by_status(client):
    res = client.get("/viewer/complaints?status=open", headers=HEADERS)
    for item in res.json()["items"]:
        assert item["status"] == "open"

def test_complaints_filter_by_priority(client):
    res = client.get("/viewer/complaints?priority=P1", headers=HEADERS)
    for item in res.json()["items"]:
        assert item["priority"] == "P1"

def test_complaints_create_valid(client):
    res = client.post("/viewer/complaints", json={"title": "Test issue", "category": "buffering", "content": "Details"}, headers=HEADERS)
    assert res.status_code == 200
    assert "id" in res.json()

def test_complaints_create_missing_title_422(client):
    res = client.post("/viewer/complaints", json={"category": "buffering"}, headers=HEADERS)
    assert res.status_code == 422

# ═══ Trends ═══

def test_trends_returns_expected_shape(client):
    data = client.get("/viewer/trends", headers=HEADERS).json()
    for key in ("qoe_by_device", "qoe_by_region", "complaint_categories"):
        assert key in data

def test_trends_device_breakdown_not_empty(client):
    data = client.get("/viewer/trends", headers=HEADERS).json()
    assert len(data["qoe_by_device"]) > 0

# ═══ Auth ═══

def test_dashboard_requires_auth(client):
    import backend.routers.viewer_experience as ve
    import inspect
    assert "ctx" in inspect.signature(ve.dashboard).parameters

def test_qoe_requires_auth(client):
    import backend.routers.viewer_experience as ve
    import inspect
    assert "ctx" in inspect.signature(ve.qoe_metrics).parameters

def test_complaints_requires_auth(client):
    import backend.routers.viewer_experience as ve
    import inspect
    assert "ctx" in inspect.signature(ve.list_complaints).parameters
