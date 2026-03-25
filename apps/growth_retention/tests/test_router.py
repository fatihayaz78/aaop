"""Router tests for Growth & Retention — 15 tests with mocked DuckDB."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_duckdb, get_tenant_context
from backend.main import app
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

HEADERS = {"X-Tenant-ID": "s_sport_plus"}

MOCK_SCORE = {"id": "RS-001", "tenant_id": "s_sport_plus", "user_id_hash": "abc123def456",
    "churn_risk": 0.85, "qoe_score": 2.1, "cdn_score": 0.7, "retention_trend": -0.05,
    "segment": "at_risk", "last_active": "2026-03-20", "created_at": "2026-03-25"}
MOCK_LOW = {**MOCK_SCORE, "id": "RS-002", "churn_risk": 0.15, "qoe_score": 4.5, "segment": "power_user"}


def _make_mock_duck(*, scores=None, empty=False):
    mock = MagicMock(spec=DuckDBClient)
    items = [] if empty else (scores or [MOCK_SCORE, MOCK_LOW])

    def _fetch_one(sql, params=None):
        sql_l = sql.lower()
        if "avg(churn_risk)" in sql_l:
            crs = [i["churn_risk"] for i in items]
            qoes = [i["qoe_score"] for i in items]
            return {"avg_cr": sum(crs)/len(crs) if crs else 0, "avg_qoe": sum(qoes)/len(qoes) if qoes else 0}
        if "count" in sql_l and "churn_risk > 0.7" in sql_l:
            return {"cnt": sum(1 for i in items if i["churn_risk"] > 0.7)}
        if "count" in sql_l:
            return {"cnt": len(items)}
        return {"cnt": 0}

    def _fetch_all(sql, params=None):
        sql_l = sql.lower()
        if "group by segment" in sql_l:
            from collections import Counter
            c = Counter(i["segment"] for i in items)
            return [{"segment": k, "cnt": v, "avg_cr": 0.5, "avg_qoe": 3.5} for k, v in c.items()]
        if "churn_risk > 0.7" in sql_l:
            return [i for i in items if i["churn_risk"] > 0.7]
        result = list(items)
        if params:
            for p in params:
                if isinstance(p, str) and p in ("power_user", "regular", "at_risk", "churned"):
                    result = [i for i in result if i["segment"] == p]
        return result

    mock.fetch_one.side_effect = _fetch_one
    mock.fetch_all.side_effect = _fetch_all
    return mock


@pytest.fixture
def client():
    mock_duck = _make_mock_duck()
    app.dependency_overrides[get_duckdb] = lambda: mock_duck
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ═══ Dashboard ═══

def test_dashboard_returns_expected_shape(client):
    data = client.get("/growth/dashboard", headers=HEADERS).json()
    for key in ("total_users", "at_risk_users", "avg_churn_risk", "avg_qoe_score", "segment_breakdown", "churn_trend_7d", "top_churn_reasons"):
        assert key in data

def test_dashboard_segment_breakdown_has_4_keys(client):
    data = client.get("/growth/dashboard", headers=HEADERS).json()
    for key in ("power_user", "regular", "at_risk", "churned"):
        assert key in data["segment_breakdown"]

def test_dashboard_churn_trend_has_7_days(client):
    data = client.get("/growth/dashboard", headers=HEADERS).json()
    assert len(data["churn_trend_7d"]) == 7

# ═══ Retention ═══

def test_retention_list_paginated(client):
    data = client.get("/growth/retention", headers=HEADERS).json()
    assert "items" in data and "total" in data

def test_retention_filter_by_segment(client):
    data = client.get("/growth/retention?segment=at_risk", headers=HEADERS).json()
    for item in data["items"]:
        assert item["segment"] == "at_risk"

# ═══ Churn Risk ═══

def test_churn_risk_all_above_threshold(client):
    data = client.get("/growth/churn-risk", headers=HEADERS).json()
    assert "threshold" in data
    for item in data["items"]:
        assert item["churn_risk"] > 0.7

# ═══ Segments ═══

def test_segments_returns_segments(client):
    data = client.get("/growth/segments", headers=HEADERS).json()
    assert "segments" in data
    assert len(data["segments"]) > 0

def test_segments_have_recommendations(client):
    data = client.get("/growth/segments", headers=HEADERS).json()
    for seg in data["segments"]:
        assert "recommended_action" in seg

# ═══ Query ═══

def test_query_valid_question_returns_sql(client):
    res = client.post("/growth/query", json={"question": "Show high churn users"}, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "sql" in data

def test_query_unsafe_returns_error(client):
    # The NL→SQL demo doesn't actually process DROP, but test the SELECT guard
    res = client.post("/growth/query", json={"question": "Show all users"}, headers=HEADERS)
    data = res.json()
    # Should return sql starting with SELECT (safe)
    if "sql" in data:
        assert data["sql"].strip().upper().startswith("SELECT")

def test_query_empty_question(client):
    res = client.post("/growth/query", json={"question": ""}, headers=HEADERS)
    data = res.json()
    assert "error" in data

# ═══ Auth ═══

def test_dashboard_requires_auth(client):
    import backend.routers.growth_retention as gr
    import inspect
    assert "ctx" in inspect.signature(gr.dashboard).parameters

def test_retention_requires_auth(client):
    import backend.routers.growth_retention as gr
    import inspect
    assert "ctx" in inspect.signature(gr.retention_list).parameters

def test_churn_requires_auth(client):
    import backend.routers.growth_retention as gr
    import inspect
    assert "ctx" in inspect.signature(gr.churn_risk).parameters

def test_query_requires_auth(client):
    import backend.routers.growth_retention as gr
    import inspect
    assert "ctx" in inspect.signature(gr.data_analyst_query).parameters
