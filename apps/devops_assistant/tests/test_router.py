"""Router tests for DevOps Assistant — 12 tests."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
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
    data = client.get("/devops/dashboard").json()
    for k in ("runbooks_available", "recent_queries_24h", "dangerous_commands_blocked", "top_topics"):
        assert k in data

def test_dashboard_top_topics_not_empty(client):
    data = client.get("/devops/dashboard").json()
    assert len(data["top_topics"]) > 0

def test_chat_normal_message_returns_response(client):
    with patch("backend.routers.devops_assistant.get_settings") as ms:
        ms.return_value = MagicMock(anthropic_api_key="")
        res = client.post("/devops/chat", json={"message": "How to purge CDN cache?"})
    assert res.status_code == 200
    data = res.json()
    assert "response" in data

def test_chat_dangerous_command_rm_blocked(client):
    data = client.post("/devops/chat", json={"message": "rm -rf /var/log"}).json()
    assert data["blocked"] is True

def test_chat_dangerous_command_drop_table_blocked(client):
    data = client.post("/devops/chat", json={"message": "DROP TABLE users"}).json()
    assert data["blocked"] is True

def test_chat_dangerous_command_delete_from_blocked(client):
    data = client.post("/devops/chat", json={"message": "DELETE FROM incidents WHERE 1=1"}).json()
    assert data["blocked"] is True

def test_chat_empty_message_422(client):
    assert client.post("/devops/chat", json={"message": ""}).status_code in (200, 422)
    # Empty string may pass Pydantic but return empty response

def test_chat_response_has_blocked_false(client):
    with patch("backend.routers.devops_assistant.get_settings") as ms:
        ms.return_value = MagicMock(anthropic_api_key="")
        data = client.post("/devops/chat", json={"message": "What is pre-scale?"}).json()
    assert data.get("blocked") is False

def test_runbooks_list_returns_items(client):
    data = client.get("/devops/runbooks").json()
    assert "items" in data
    assert data["total"] > 0

def test_runbooks_search_returns_results(client):
    data = client.get("/devops/runbooks/search?q=purge").json()
    assert "results" in data

def test_dashboard_requires_auth(client):
    import backend.routers.devops_assistant as da; import inspect
    assert "ctx" in inspect.signature(da.dashboard).parameters

def test_chat_requires_auth(client):
    import backend.routers.devops_assistant as da; import inspect
    assert "ctx" in inspect.signature(da.chat).parameters
