"""Tests for Growth & Retention schemas."""

from __future__ import annotations

from apps.growth_retention.schemas import (
    ChurnRiskResult,
    CustomerSegment,
    GrowthInsight,
    NLQueryResult,
    RetentionCampaign,
    RetentionScore,
)


def test_retention_score_defaults():
    s = RetentionScore(tenant_id="t1", segment_id="seg1", churn_risk=0.75)
    assert s.score_id.startswith("RS-")
    assert s.churn_risk == 0.75
    assert s.retention_7d is None


def test_customer_segment():
    seg = CustomerSegment(tenant_id="t1", name="high_risk", size=500, avg_churn_risk=0.8)
    assert seg.segment_id.startswith("SEG-")
    assert seg.size == 500


def test_churn_risk_result():
    r = ChurnRiskResult(tenant_id="t1", segment_id="s1", churn_risk=0.9, recommendation="Retain")
    assert r.churn_risk == 0.9


def test_growth_insight():
    i = GrowthInsight(tenant_id="t1", category="retention", title="High churn")
    assert i.insight_id.startswith("INS-")
    assert i.impact_score == 0.0


def test_nl_query_result():
    r = NLQueryResult(query="how many users?", generated_sql="SELECT COUNT(*) FROM ...", row_count=42)
    assert r.row_count == 42
    assert r.columns == []


def test_retention_campaign():
    c = RetentionCampaign(tenant_id="t1", segment_id="s1", campaign_type="email")
    assert c.campaign_id.startswith("CMP-")
    assert c.status == "pending"
