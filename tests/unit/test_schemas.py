"""Tests for shared/schemas/."""

from __future__ import annotations

from shared.schemas.agent_decision import AgentDecision
from shared.schemas.base_event import BaseEvent, RiskLevel, SeverityLevel, TenantContext


def test_severity_level_values():
    assert SeverityLevel.P0 == "P0"
    assert SeverityLevel.P3 == "P3"


def test_risk_level_values():
    assert RiskLevel.LOW == "LOW"
    assert RiskLevel.HIGH == "HIGH"


def test_tenant_context():
    ctx = TenantContext(tenant_id="bein_sports", user_id="u1", role="admin")
    assert ctx.tenant_id == "bein_sports"
    assert ctx.role == "admin"


def test_tenant_context_optional_fields():
    ctx = TenantContext(tenant_id="test")
    assert ctx.user_id is None
    assert ctx.role is None


def test_base_event_defaults():
    evt = BaseEvent(event_type="test_event", tenant_id="t1", source_app="test_app")
    assert evt.event_id  # auto-generated
    assert evt.severity == SeverityLevel.P3
    assert evt.payload == {}
    assert evt.correlation_ids == []


def test_base_event_custom():
    evt = BaseEvent(
        event_type="cdn_anomaly_detected",
        tenant_id="bein",
        source_app="log_analyzer",
        severity=SeverityLevel.P1,
        payload={"error_rate": 0.067},
    )
    assert evt.severity == SeverityLevel.P1
    assert evt.payload["error_rate"] == 0.067


def test_agent_decision_defaults():
    d = AgentDecision(
        tenant_id="t1",
        app="ops_center",
        action="create_incident",
        risk_level=RiskLevel.MEDIUM,
        llm_model_used="claude-sonnet-4-20250514",
    )
    assert d.decision_id  # auto-generated
    assert d.approval_required is False
    assert d.tools_executed == []


def test_agent_decision_high_risk():
    d = AgentDecision(
        tenant_id="t1",
        app="ops_center",
        action="restart_service",
        risk_level=RiskLevel.HIGH,
        approval_required=True,
        llm_model_used="claude-opus-4-20250514",
        confidence_score=0.92,
    )
    assert d.approval_required is True
    assert d.risk_level == RiskLevel.HIGH
    assert d.confidence_score == 0.92
