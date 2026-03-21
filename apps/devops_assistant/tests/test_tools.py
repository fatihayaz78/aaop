"""Tests for DevOps Assistant tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.devops_assistant.schemas import Deployment, RunbookExecution
from apps.devops_assistant.tools import (
    check_service_health,
    create_deployment_record,
    execute_runbook,
    get_deployment_history,
    get_platform_metrics,
    restart_service,
    search_runbooks,
    suggest_command,
)

# ── Service health ──


@pytest.mark.asyncio
async def test_check_service_health():
    h = await check_service_health("t1", "fastapi")
    assert h.service == "fastapi"
    assert h.status == "healthy"


# ── Deployment history ──


@pytest.mark.asyncio
async def test_get_deployment_history(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"app": "backend", "action": "deploy"}])
    result = await get_deployment_history("t1", mock_db)
    assert len(result) == 1


# ── Runbook search ──


@pytest.mark.asyncio
async def test_search_runbooks(mock_chroma: MagicMock):
    results = await search_runbooks("t1", "restart CDN", mock_chroma)
    assert len(results) == 1
    assert "CDN Restart" in results[0]["metadata"]["title"]


@pytest.mark.asyncio
async def test_search_runbooks_empty(mock_chroma: MagicMock):
    mock_chroma.query = MagicMock(return_value={"documents": [], "ids": []})
    results = await search_runbooks("t1", "nothing", mock_chroma)
    assert results == []


# ── Platform metrics ──


@pytest.mark.asyncio
async def test_get_platform_metrics(mock_db: MagicMock):
    mock_db.fetch_all = MagicMock(return_value=[{"count": 3}])
    metrics = await get_platform_metrics("t1", mock_db)
    assert "open_incidents" in metrics


# ── Command suggestion ──


@pytest.mark.asyncio
async def test_suggest_safe_command():
    cmd = await suggest_command("t1", "kubectl get pods")
    assert cmd.is_dangerous is False
    assert cmd.risk_level == "LOW"


@pytest.mark.asyncio
async def test_suggest_dangerous_command():
    cmd = await suggest_command("t1", "rm -rf /tmp")
    assert cmd.is_dangerous is True
    assert cmd.risk_level == "HIGH"


# ── MEDIUM risk ──


@pytest.mark.asyncio
async def test_create_deployment_record(mock_db: MagicMock):
    dep = Deployment(tenant_id="t1", service="backend", version="2.0.0")
    result = await create_deployment_record("t1", dep, mock_db)
    assert result == dep.deployment_id
    mock_db.execute.assert_called_once()


# ── HIGH risk ──


@pytest.mark.asyncio
async def test_execute_runbook_approval():
    rb = RunbookExecution(tenant_id="t1", runbook_id="rb-1")
    result = await execute_runbook("t1", rb)
    assert result["status"] == "approval_required"


@pytest.mark.asyncio
async def test_restart_service_approval():
    result = await restart_service("t1", "fastapi", "High latency")
    assert result["status"] == "approval_required"
    assert result["service"] == "fastapi"
