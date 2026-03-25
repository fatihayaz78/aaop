"""Router tests for Knowledge Base — 12 tests."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from backend.dependencies import get_tenant_context
from backend.main import app
from shared.schemas.base_event import TenantContext

@pytest.fixture
def client():
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(tenant_id="s_sport_plus")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()

def test_dashboard_returns_expected_shape(client):
    data = client.get("/knowledge/dashboard").json()
    for k in ("total_documents", "collections", "recent_searches", "last_indexed"):
        assert k in data

def test_dashboard_collections_has_4_keys(client):
    data = client.get("/knowledge/dashboard").json()
    assert len(data["collections"]) == 4  # incidents, runbooks, platform, akamai_ds2

def test_search_returns_results(client):
    data = client.get("/knowledge/search?q=CDN+failure").json()
    assert "results" in data
    assert len(data["results"]) > 0

def test_search_missing_query(client):
    data = client.get("/knowledge/search?q=").json()
    assert data["results"] == []

def test_documents_list_requires_collection(client):
    data = client.get("/knowledge/documents?collection=incidents").json()
    assert "items" in data

def test_documents_list_incidents_collection(client):
    data = client.get("/knowledge/documents?collection=incidents").json()
    assert data["total"] > 0

def test_documents_list_runbooks_collection(client):
    data = client.get("/knowledge/documents?collection=runbooks").json()
    assert data["total"] > 0

def test_documents_create_valid(client):
    res = client.post("/knowledge/documents", json={"title": "Test Doc", "content": "Content here", "collection": "platform"})
    assert res.status_code == 200
    assert "id" in res.json()

def test_documents_create_missing_title_422(client):
    assert client.post("/knowledge/documents", json={"content": "X"}).status_code == 422

def test_documents_delete_returns_approval_required(client):
    data = client.delete("/knowledge/documents/doc-001").json()
    assert data["approval_required"] is True

def test_dashboard_requires_auth(client):
    import backend.routers.knowledge_base as kb; import inspect
    assert "ctx" in inspect.signature(kb.dashboard).parameters

def test_search_requires_auth(client):
    import backend.routers.knowledge_base as kb; import inspect
    assert "ctx" in inspect.signature(kb.search).parameters
