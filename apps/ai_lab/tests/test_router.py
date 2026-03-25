"""Router tests for AI Lab — 12 tests with mocked DuckDB."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.dependencies import get_duckdb, get_tenant_context
from backend.main import app
from shared.clients.duckdb_client import DuckDBClient
from shared.schemas.base_event import TenantContext

MOCK_EXP = {"id": "EXP-001", "tenant_id": "s_sport_plus", "name": "Test AB", "hypothesis": "H1",
    "status": "completed", "variant_a": "A", "variant_b": "B", "sample_size": 1000,
    "p_value": 0.03, "winner": "variant_a", "created_at": "2026-03-25", "completed_at": "2026-03-25"}
MOCK_MODEL = {"id": "MOD-001", "tenant_id": "s_sport_plus", "model_name": "claude-sonnet-rca",
    "version": "v3.0", "status": "production", "accuracy": 0.94, "latency_ms": 320,
    "deployed_at": "2026-03-20", "created_at": "2026-03-15"}

def _make_mock(*, exps=None, models=None):
    mock = MagicMock(spec=DuckDBClient)
    _e = exps or [MOCK_EXP]
    _m = models or [MOCK_MODEL]
    def _one(sql, params=None):
        sql_l = sql.lower()
        if "experiments" in sql_l and "id = ?" in sql_l and params:
            return next((e for e in _e if e["id"] == params[0]), None)
        if "model_registry" in sql_l and "id = ?" in sql_l and params:
            return next((m for m in _m if m["id"] == params[0]), None)
        if "avg(accuracy)" in sql_l:
            return {"avg_acc": 0.92}
        if "count" in sql_l and "running" in sql_l:
            return {"cnt": sum(1 for e in _e if e["status"] == "running")}
        if "count" in sql_l and "completed" in sql_l:
            return {"cnt": sum(1 for e in _e if e["status"] == "completed")}
        if "count" in sql_l and "production" in sql_l:
            return {"cnt": sum(1 for m in _m if m["status"] == "production")}
        if "count" in sql_l:
            return {"cnt": len(_e)}
        return {"cnt": 0}
    def _all(sql, params=None):
        sql_l = sql.lower()
        if "model_registry" in sql_l:
            result = list(_m)
            if params:
                for p in params:
                    if isinstance(p, str) and p in ("production", "staging", "deprecated"):
                        result = [m for m in result if m["status"] == p]
            return result
        result = list(_e)
        if params:
            for p in params:
                if isinstance(p, str) and p in ("draft", "running", "completed"):
                    result = [e for e in result if e["status"] == p]
        return result
    mock.fetch_one.side_effect = _one
    mock.fetch_all.side_effect = _all
    mock.execute.return_value = None
    return mock

@pytest.fixture
def client():
    app.dependency_overrides[get_duckdb] = lambda: _make_mock()
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()

def test_dashboard_returns_expected_shape(client):
    data = client.get("/ai-lab/dashboard").json()
    for k in ("total_experiments", "running_experiments", "completed_experiments", "models_in_production", "avg_model_accuracy", "recent_experiments"):
        assert k in data

def test_experiments_list_paginated(client):
    data = client.get("/ai-lab/experiments").json()
    assert "items" in data and "total" in data

def test_experiments_filter_by_status(client):
    data = client.get("/ai-lab/experiments?status=completed").json()
    for item in data["items"]:
        assert item["status"] == "completed"

def test_experiment_detail_found(client):
    data = client.get("/ai-lab/experiments/EXP-001").json()
    assert data.get("id") == "EXP-001"

def test_experiment_detail_not_found(client):
    data = client.get("/ai-lab/experiments/NOPE").json()
    assert "error" in data

def test_experiment_create_valid(client):
    res = client.post("/ai-lab/experiments", json={"name": "Test", "hypothesis": "H", "variant_a": "A", "variant_b": "B", "sample_size": 500})
    assert res.status_code == 200
    assert "id" in res.json()

def test_experiment_create_missing_name_422(client):
    assert client.post("/ai-lab/experiments", json={"hypothesis": "H"}).status_code == 422

def test_models_list_returns_items(client):
    data = client.get("/ai-lab/models").json()
    assert "items" in data

def test_models_filter_by_status(client):
    data = client.get("/ai-lab/models?status=production").json()
    for item in data["items"]:
        assert item["status"] == "production"

def test_model_detail_found(client):
    assert client.get("/ai-lab/models/MOD-001").json().get("id") == "MOD-001"

def test_dashboard_requires_auth(client):
    import backend.routers.ai_lab as al; import inspect
    assert "ctx" in inspect.signature(al.dashboard).parameters

def test_experiments_requires_auth(client):
    import backend.routers.ai_lab as al; import inspect
    assert "ctx" in inspect.signature(al.list_experiments).parameters
