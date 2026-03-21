"""Tests for DevOps Assistant schemas."""

from __future__ import annotations

from apps.devops_assistant.schemas import CommandSuggestion, Deployment, RunbookExecution, ServiceHealth


def test_service_health():
    h = ServiceHealth(service="fastapi", status="healthy", latency_ms=25)
    assert h.status == "healthy"


def test_deployment():
    d = Deployment(tenant_id="t1", service="backend", version="1.2.3")
    assert d.deployment_id.startswith("DEP-")
    assert d.status == "pending"


def test_command_suggestion_safe():
    c = CommandSuggestion(command="kubectl get pods", is_dangerous=False)
    assert c.risk_level == "LOW"


def test_command_suggestion_dangerous():
    c = CommandSuggestion(command="rm -rf /", is_dangerous=True, risk_level="HIGH")
    assert c.is_dangerous is True


def test_runbook_execution():
    r = RunbookExecution(tenant_id="t1", runbook_id="rb-1", total_steps=5)
    assert r.execution_id.startswith("RBX-")
    assert r.status == "pending"
