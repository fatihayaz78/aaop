"""Tests for Ops Center schemas."""

from __future__ import annotations

from apps.ops_center.schemas import (
    Incident,
    IncidentCreate,
    OpsMetrics,
    RCARequest,
    RCAResult,
)
from shared.schemas.base_event import SeverityLevel


def test_incident_create():
    ic = IncidentCreate(
        tenant_id="bein", severity=SeverityLevel.P1,
        title="CDN Spike", description="Error rate >5%",
    )
    assert ic.tenant_id == "bein"
    assert ic.severity == SeverityLevel.P1


def test_incident_defaults():
    inc = Incident(tenant_id="t1", severity=SeverityLevel.P2, title="Test")
    assert inc.incident_id.startswith("INC-")
    assert inc.status == "open"
    assert inc.summary_tr == ""
    assert inc.detail_en == ""
    assert inc.rca_id is None


def test_incident_with_bilingual():
    inc = Incident(
        tenant_id="t1", severity=SeverityLevel.P1, title="CDN Issue",
        summary_tr="CDN hata oranı yüksek.",
        detail_en="Error rate exceeded threshold.",
    )
    assert inc.summary_tr == "CDN hata oranı yüksek."
    assert inc.detail_en == "Error rate exceeded threshold."


def test_rca_result_defaults():
    rca = RCAResult(incident_id="INC-1", tenant_id="t1")
    assert rca.rca_id.startswith("RCA-")
    assert rca.confidence_score == 0.0
    assert rca.root_cause == ""


def test_rca_result_full():
    rca = RCAResult(
        incident_id="INC-1", tenant_id="t1",
        root_cause="Connection pool exhaustion",
        confidence_score=0.92,
        summary_tr="Bağlantı havuzu doldu.",
        detail_en="Origin connection pool maxed out.",
    )
    assert rca.confidence_score == 0.92
    assert rca.root_cause == "Connection pool exhaustion"


def test_rca_request():
    r = RCARequest(incident_id="INC-1", tenant_id="t1")
    assert r.incident_id == "INC-1"


def test_ops_metrics_defaults():
    m = OpsMetrics(tenant_id="t1")
    assert m.active_incidents == 0
    assert m.avg_mttr_seconds == 0.0


def test_incident_severity_values():
    for sev in ["P0", "P1", "P2", "P3"]:
        inc = Incident(tenant_id="t1", severity=SeverityLevel(sev), title="Test")
        assert inc.severity == sev
