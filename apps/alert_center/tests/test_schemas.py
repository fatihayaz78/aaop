"""Tests for Alert Center schemas."""

from __future__ import annotations

from datetime import datetime

from apps.alert_center.schemas import (
    Alert,
    AlertChannel,
    AlertRule,
    RoutingDecision,
    SuppressionRule,
    compute_fingerprint,
)
from shared.schemas.base_event import SeverityLevel


def test_alert_defaults():
    a = Alert(tenant_id="t1", source_app="ops", event_type="incident", severity=SeverityLevel.P1, title="Test")
    assert a.alert_id.startswith("ALT-")
    assert a.status == "sent"
    assert a.channels_routed == []


def test_alert_rule():
    r = AlertRule(
        tenant_id="t1", name="CDN Alerts",
        event_types=["cdn_anomaly_detected"], severity_min=SeverityLevel.P2,
        channels=["slack"],
    )
    assert r.is_active is True
    assert "cdn_anomaly_detected" in r.event_types


def test_alert_channel():
    c = AlertChannel(
        tenant_id="t1", channel_type="slack",
        name="#ops", config_json={"webhook": "https://hooks.slack.com/xxx"},
    )
    assert c.channel_type == "slack"


def test_suppression_rule():
    s = SuppressionRule(
        tenant_id="t1", name="Maintenance",
        start_time=datetime(2026, 3, 19, 2, 0),
        end_time=datetime(2026, 3, 19, 4, 0),
    )
    assert s.is_active is True


def test_routing_decision():
    alert = Alert(tenant_id="t1", source_app="ops", event_type="incident", severity=SeverityLevel.P0, title="Outage")
    d = RoutingDecision(alert=alert, action="route", channels=["slack", "pagerduty"], approval_required=True)
    assert d.approval_required is True
    assert len(d.channels) == 2


def test_fingerprint_deterministic():
    fp1 = compute_fingerprint("t1", "ops", "incident", "P1")
    fp2 = compute_fingerprint("t1", "ops", "incident", "P1")
    fp3 = compute_fingerprint("t1", "ops", "incident", "P2")
    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 24


def test_fingerprint_different_tenants():
    fp1 = compute_fingerprint("t1", "ops", "incident", "P1")
    fp2 = compute_fingerprint("t2", "ops", "incident", "P1")
    assert fp1 != fp2
