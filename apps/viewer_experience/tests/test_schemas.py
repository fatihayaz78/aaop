"""Tests for Viewer Experience schemas."""

from __future__ import annotations

from apps.viewer_experience.schemas import Complaint, ComplaintAnalysis, QoEAnomaly, QoESession


def test_qoe_session_defaults():
    s = QoESession(tenant_id="t1")
    assert s.session_id
    assert s.quality_score == 0.0
    assert s.errors == []


def test_qoe_anomaly():
    a = QoEAnomaly(session_id="s1", tenant_id="t1", quality_score=1.8, reason="high_buffering")
    assert a.severity == "P2"


def test_complaint_defaults():
    c = Complaint(tenant_id="t1")
    assert c.id.startswith("CMP-")
    assert c.status == "open"
    assert c.similar_complaint_ids == []


def test_complaint_analysis():
    ca = ComplaintAnalysis(complaint_id="c1", category="buffering", sentiment="negative", priority="P2")
    assert ca.similar_count == 0
