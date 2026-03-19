"""Tests for Ops Center tools — risk levels and behavior."""

from __future__ import annotations

import asyncio

import pytest

from apps.ops_center.schemas import Incident, RCAResult
from apps.ops_center.tools import (
    correlate_events,
    escalate_to_oncall,
    execute_remediation,
    publish_incident_created,
    publish_rca_completed,
    send_slack_notification,
)
from shared.event_bus import EventBus, EventType
from shared.schemas.base_event import SeverityLevel


@pytest.mark.asyncio
async def test_correlate_events_with_cdn():
    incident = Incident(
        tenant_id="t1", severity=SeverityLevel.P1, title="Test",
        affected_services=["cdn"],
    )
    cdn_data = [{"analysis_id": "a1", "error_rate": 0.07}]
    result = await correlate_events("t1", incident, cdn_data, [])
    assert result["cdn_anomalies_found"] == 1
    assert result["cdn_error_rate"] == 0.07


@pytest.mark.asyncio
async def test_correlate_events_empty():
    incident = Incident(tenant_id="t1", severity=SeverityLevel.P3, title="Test")
    result = await correlate_events("t1", incident, [], [])
    assert result["cdn_anomalies_found"] == 0
    assert result["qoe_issues_found"] == 0


@pytest.mark.asyncio
async def test_correlate_events_with_qoe():
    incident = Incident(tenant_id="t1", severity=SeverityLevel.P2, title="QoE Issue")
    qoe_data = [{"session_id": "s1"}, {"session_id": "s2"}]
    result = await correlate_events("t1", incident, [], qoe_data)
    assert result["qoe_affected_sessions"] == 2


@pytest.mark.asyncio
async def test_execute_remediation_requires_approval():
    result = await execute_remediation("t1", "restart_cdn", "edge-eu-1")
    assert result["status"] == "approval_required"
    assert result["action"] == "restart_cdn"


@pytest.mark.asyncio
async def test_escalate_to_oncall_requires_approval():
    result = await escalate_to_oncall("t1", "INC-001", urgency="critical")
    assert result["status"] == "approval_required"
    assert result["urgency"] == "critical"


@pytest.mark.asyncio
async def test_send_slack_notification():
    result = await send_slack_notification("t1", "Test alert", "#ops-alerts")
    assert result["status"] == "sent"
    assert result["channel"] == "#ops-alerts"


@pytest.mark.asyncio
async def test_publish_incident_created(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.INCIDENT_CREATED, handler)
    await event_bus.start()

    incident = Incident(tenant_id="t1", severity=SeverityLevel.P1, title="CDN Spike")
    await publish_incident_created("t1", incident, event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_rca_completed(event_bus: EventBus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe(EventType.RCA_COMPLETED, handler)
    await event_bus.start()

    rca = RCAResult(incident_id="INC-1", tenant_id="t1", root_cause="Pool exhaustion")
    await publish_rca_completed("t1", rca, event_bus)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].payload["root_cause"] == "Pool exhaustion"
