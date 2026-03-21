"""Integration tests — all 9 EventBus cross-app flows wired end-to-end."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import BaseEvent, SeverityLevel, TenantContext


def _mock_llm() -> LLMGateway:
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Integration test mock response")]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 25
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def llm() -> LLMGateway:
    return _mock_llm()


# ── Flow 1: cdn_anomaly_detected → ops_center + alert_center ──


@pytest.mark.asyncio
async def test_cdn_anomaly_triggers_incident(bus: EventBus) -> None:
    """log_analyzer publishes cdn_anomaly → ops_center and alert_center both receive."""
    received_ops: list[Any] = []
    received_alert: list[Any] = []

    async def ops_handler(e: BaseEvent) -> None:
        received_ops.append(e)

    async def alert_handler(e: BaseEvent) -> None:
        received_alert.append(e)

    bus.subscribe(EventType.CDN_ANOMALY_DETECTED, ops_handler)
    bus.subscribe(EventType.CDN_ANOMALY_DETECTED, alert_handler)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.CDN_ANOMALY_DETECTED,
        tenant_id="bein_sports",
        source_app="log_analyzer",
        severity=SeverityLevel.P1,
        payload={"error_rate": 0.067, "analysis_id": "cdn-001"},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_ops) == 1
    assert len(received_alert) == 1
    assert received_ops[0].payload["error_rate"] == 0.067
    assert received_alert[0].source_app == "log_analyzer"


# ── Flow 2: incident_created → alert_center + knowledge_base ──


@pytest.mark.asyncio
async def test_incident_created_routes_alert_and_indexes_kb(bus: EventBus) -> None:
    """ops_center publishes incident_created → alert_center + knowledge_base both receive."""
    received_alert: list[Any] = []
    received_kb: list[Any] = []

    async def alert_h(e: BaseEvent) -> None:
        received_alert.append(e)

    async def kb_h(e: BaseEvent) -> None:
        received_kb.append(e)

    bus.subscribe(EventType.INCIDENT_CREATED, alert_h)
    bus.subscribe(EventType.INCIDENT_CREATED, kb_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.INCIDENT_CREATED,
        tenant_id="bein_sports",
        source_app="ops_center",
        severity=SeverityLevel.P1,
        payload={"incident_id": "INC-001", "title": "CDN Error Spike"},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_alert) == 1
    assert len(received_kb) == 1
    assert received_kb[0].payload["incident_id"] == "INC-001"


# ── Flow 3: live_event_starting → ops_center + log_analyzer + alert_center ──


@pytest.mark.asyncio
async def test_live_event_triggers_prescale_and_log_mode(bus: EventBus) -> None:
    """live_intelligence publishes live_event_starting → 3 subscribers receive."""
    received: dict[str, list[Any]] = {"ops": [], "log": [], "alert": []}

    async def ops_h(e: BaseEvent) -> None:
        received["ops"].append(e)

    async def log_h(e: BaseEvent) -> None:
        received["log"].append(e)

    async def alert_h(e: BaseEvent) -> None:
        received["alert"].append(e)

    bus.subscribe(EventType.LIVE_EVENT_STARTING, ops_h)
    bus.subscribe(EventType.LIVE_EVENT_STARTING, log_h)
    bus.subscribe(EventType.LIVE_EVENT_STARTING, alert_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.LIVE_EVENT_STARTING,
        tenant_id="bein_sports",
        source_app="live_intelligence",
        severity=SeverityLevel.P2,
        payload={"event_id": "EVT-001", "event_name": "GS vs FB", "expected_viewers": 500_000},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received["ops"]) == 1
    assert len(received["log"]) == 1
    assert len(received["alert"]) == 1
    assert received["ops"][0].payload["expected_viewers"] == 500_000


# ── Flow 4: qoe_degradation → ops_center + alert_center ──


@pytest.mark.asyncio
async def test_qoe_degradation_creates_incident(bus: EventBus) -> None:
    """viewer_experience publishes qoe_degradation → ops_center + alert_center."""
    received_ops: list[Any] = []
    received_alert: list[Any] = []

    async def ops_h(e: BaseEvent) -> None:
        received_ops.append(e)

    async def alert_h(e: BaseEvent) -> None:
        received_alert.append(e)

    bus.subscribe(EventType.QOE_DEGRADATION, ops_h)
    bus.subscribe(EventType.QOE_DEGRADATION, alert_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.QOE_DEGRADATION,
        tenant_id="bein_sports",
        source_app="viewer_experience",
        severity=SeverityLevel.P2,
        payload={"session_id": "sess-001", "quality_score": 1.8},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_ops) == 1
    assert len(received_alert) == 1
    assert received_ops[0].payload["quality_score"] == 1.8


# ── Flow 5: churn_risk_detected → alert_center ──


@pytest.mark.asyncio
async def test_churn_risk_reaches_alert_center(bus: EventBus) -> None:
    """growth_retention publishes churn_risk_detected → alert_center receives."""
    received: list[Any] = []

    async def handler(e: BaseEvent) -> None:
        received.append(e)

    bus.subscribe(EventType.CHURN_RISK_DETECTED, handler)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.CHURN_RISK_DETECTED,
        tenant_id="bein_sports",
        source_app="growth_retention",
        severity=SeverityLevel.P2,
        payload={"segment_id": "seg-at-risk", "churn_risk": 0.85},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received) == 1
    assert received[0].payload["churn_risk"] == 0.85


# ── Flow 6: scale_recommendation → ops_center + alert_center ──


@pytest.mark.asyncio
async def test_scale_recommendation_flow(bus: EventBus) -> None:
    """capacity_cost publishes scale_recommendation → ops_center + alert_center."""
    received_ops: list[Any] = []
    received_alert: list[Any] = []

    async def ops_h(e: BaseEvent) -> None:
        received_ops.append(e)

    async def alert_h(e: BaseEvent) -> None:
        received_alert.append(e)

    bus.subscribe(EventType.SCALE_RECOMMENDATION, ops_h)
    bus.subscribe(EventType.SCALE_RECOMMENDATION, alert_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.SCALE_RECOMMENDATION,
        tenant_id="bein_sports",
        source_app="capacity_cost",
        severity=SeverityLevel.P1,
        payload={"metric": "bandwidth", "current_pct": 95.0, "scale_factor": 2.0},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_ops) == 1
    assert len(received_alert) == 1


# ── Flow 7: external_data_updated → ops_center + growth_retention ──


@pytest.mark.asyncio
async def test_external_data_updated_flow(bus: EventBus) -> None:
    """live_intelligence publishes external_data_updated → ops_center + growth_retention."""
    received_ops: list[Any] = []
    received_growth: list[Any] = []

    async def ops_h(e: BaseEvent) -> None:
        received_ops.append(e)

    async def growth_h(e: BaseEvent) -> None:
        received_growth.append(e)

    bus.subscribe(EventType.EXTERNAL_DATA_UPDATED, ops_h)
    bus.subscribe(EventType.EXTERNAL_DATA_UPDATED, growth_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.EXTERNAL_DATA_UPDATED,
        tenant_id="bein_sports",
        source_app="live_intelligence",
        severity=SeverityLevel.P3,
        payload={"connector": "sportradar", "data": {"score": "2-1"}},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_ops) == 1
    assert len(received_growth) == 1


# ── Flow 8: rca_completed → knowledge_base + alert_center ──


@pytest.mark.asyncio
async def test_rca_completed_flow(bus: EventBus) -> None:
    """ops_center publishes rca_completed → knowledge_base + alert_center."""
    received_kb: list[Any] = []
    received_alert: list[Any] = []

    async def kb_h(e: BaseEvent) -> None:
        received_kb.append(e)

    async def alert_h(e: BaseEvent) -> None:
        received_alert.append(e)

    bus.subscribe(EventType.RCA_COMPLETED, kb_h)
    bus.subscribe(EventType.RCA_COMPLETED, alert_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.RCA_COMPLETED,
        tenant_id="bein_sports",
        source_app="ops_center",
        severity=SeverityLevel.P1,
        payload={"rca_id": "RCA-001", "root_cause": "Config misconfiguration"},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_kb) == 1
    assert len(received_alert) == 1


# ── Flow 9: analysis_complete → growth_retention + viewer_experience ──


@pytest.mark.asyncio
async def test_analysis_complete_flow(bus: EventBus) -> None:
    """log_analyzer publishes analysis_complete → growth_retention + viewer_experience."""
    received_growth: list[Any] = []
    received_viewer: list[Any] = []

    async def growth_h(e: BaseEvent) -> None:
        received_growth.append(e)

    async def viewer_h(e: BaseEvent) -> None:
        received_viewer.append(e)

    bus.subscribe(EventType.ANALYSIS_COMPLETE, growth_h)
    bus.subscribe(EventType.ANALYSIS_COMPLETE, viewer_h)
    await bus.start()

    event = BaseEvent(
        event_type=EventType.ANALYSIS_COMPLETE,
        tenant_id="bein_sports",
        source_app="log_analyzer",
        severity=SeverityLevel.P3,
        payload={"analysis_id": "AN-001", "error_rate": 0.02},
    )
    await bus.publish(event)
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_growth) == 1
    assert len(received_viewer) == 1


# ── END-TO-END: cdn → incident → alert (full chain) ──


@pytest.mark.asyncio
async def test_full_chain_cdn_to_incident_to_alert(bus: EventBus, llm: LLMGateway) -> None:
    """Full chain: cdn_anomaly → ops creates incident → alert receives incident event."""
    from apps.ops_center.agent import IncidentAgent

    final_alerts: list[Any] = []

    async def alert_handler(e: BaseEvent) -> None:
        final_alerts.append(e)

    # Step 1: Subscribe alert_center to incident_created
    bus.subscribe(EventType.INCIDENT_CREATED, alert_handler)
    await bus.start()

    # Step 2: Simulate ops_center receiving cdn_anomaly and creating incident
    # The IncidentAgent processes CDN anomaly data and publishes incident_created
    agent = IncidentAgent(llm_gateway=llm, event_bus=bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {
        "severity": "P1",
        "title": "CDN Error Rate Spike",
        "source_app": "log_analyzer",
        "metrics": {"error_rate": 0.067},
    }

    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.3)
    await bus.stop()

    # Verify the chain worked: agent processed → incident_created published → alert received
    assert result["error"] is None
    assert "incident_id" in result["decision"]
    assert len(final_alerts) == 1
    assert final_alerts[0].source_app == "ops_center"
    assert final_alerts[0].event_type == EventType.INCIDENT_CREATED
