"""Tests for IncidentAgent and RCAAgent."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.ops_center.agent import IncidentAgent, RCAAgent, _parse_bilingual
from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── IncidentAgent tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_incident_agent_p1(mock_llm: LLMGateway, event_bus: EventBus):
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {
        "event_type": "cdn_anomaly_detected",
        "severity": "P1",
        "title": "CDN Error Rate Spike",
        "description": "Error rate exceeded 5%",
        "source_app": "log_analyzer",
        "affected_services": ["cdn", "player"],
        "metrics": {"error_rate": 0.067},
        "correlation_ids": ["cdn-anomaly-001"],
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert result.get("error") is None
    output = result["output"]
    assert output["severity"] == "P1"
    assert output["rca_triggered"] is True
    assert output["incident_id"]
    assert output["summary_tr"]  # Turkish summary present


@pytest.mark.asyncio
async def test_incident_agent_p3_no_rca(mock_llm: LLMGateway, event_bus: EventBus):
    """P3 incidents should NOT trigger RCA."""
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    input_data = {"severity": "P3", "title": "Minor log warning"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["rca_triggered"] is False


@pytest.mark.asyncio
async def test_incident_agent_p0_triggers_rca(mock_llm: LLMGateway, event_bus: EventBus):
    """P0 incidents should trigger RCA."""
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    input_data = {"severity": "P0", "title": "Total CDN outage"}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["rca_triggered"] is True


@pytest.mark.asyncio
async def test_incident_publishes_event(mock_llm: LLMGateway, event_bus: EventBus):
    received: list[Any] = []

    async def handler(event: Any) -> None:
        received.append(event)

    event_bus.subscribe(EventType.INCIDENT_CREATED, handler)
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"severity": "P1", "title": "Test"})
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].event_type == "incident_created"


@pytest.mark.asyncio
async def test_incident_model_routing_p1(mock_llm: LLMGateway, event_bus: EventBus):
    """P1 should use Opus model."""
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"severity": "P1", "title": "Test"})
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "opus" in model_used


@pytest.mark.asyncio
async def test_incident_model_routing_p2(mock_llm: LLMGateway, event_bus: EventBus):
    """P2 should use Sonnet model."""
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"severity": "P2", "title": "Medium issue"})
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "sonnet" in model_used


@pytest.mark.asyncio
async def test_incident_model_routing_p3(mock_llm: LLMGateway, event_bus: EventBus):
    """P3 should use Haiku model (batch/low priority)."""
    agent = IncidentAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"severity": "P3", "title": "Minor"})
    await event_bus.stop()

    call_kwargs = mock_llm._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "haiku" in model_used


# ── RCAAgent tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_rca_agent_run(mock_llm_rca: LLMGateway, event_bus: EventBus):
    agent = RCAAgent(llm_gateway=mock_llm_rca, event_bus=event_bus)
    ctx = TenantContext(tenant_id="bein_sports")
    input_data = {
        "incident_id": "INC-test123",
        "severity": "P1",
        "title": "CDN Error Spike",
        "description": "Akamai error rate >5%",
        "affected_services": ["cdn"],
        "metrics": {"error_rate": 0.07},
        "cdn_data": [{"analysis_id": "a1", "error_rate": 0.07}],
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert result.get("error") is None
    output = result["output"]
    assert output["rca_id"]
    assert output["incident_id"] == "INC-test123"
    assert output["confidence_score"] == 0.85


@pytest.mark.asyncio
async def test_rca_always_uses_opus(mock_llm_rca: LLMGateway, event_bus: EventBus):
    """RCA should always use Opus regardless of severity."""
    agent = RCAAgent(llm_gateway=mock_llm_rca, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"incident_id": "INC-1", "severity": "P1", "title": "Test"})
    await event_bus.stop()

    call_kwargs = mock_llm_rca._anthropic.messages.create.call_args
    model_used = call_kwargs.kwargs.get("model", "")
    assert "opus" in model_used


@pytest.mark.asyncio
async def test_rca_publishes_event(mock_llm_rca: LLMGateway, event_bus: EventBus):
    received: list[Any] = []

    async def handler(event: Any) -> None:
        received.append(event)

    event_bus.subscribe(EventType.RCA_COMPLETED, handler)
    agent = RCAAgent(llm_gateway=mock_llm_rca, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    await agent.run(ctx, input_data={"incident_id": "INC-1", "severity": "P1", "title": "Test"})
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].event_type == "rca_completed"
    assert received[0].payload["incident_id"] == "INC-1"


@pytest.mark.asyncio
async def test_rca_skips_p3(mock_llm_rca: LLMGateway, event_bus: EventBus):
    """RCA should skip non-P0/P1 incidents."""
    agent = RCAAgent(llm_gateway=mock_llm_rca, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    result = await agent.run(ctx, input_data={"incident_id": "INC-1", "severity": "P3", "title": "Minor"})

    output = result["output"]
    assert output["action"] == "skipped"


# ── Bilingual parser tests ──────────────────────────────


def test_parse_bilingual_full():
    text = "TÜRKÇE ÖZET: CDN hata oranı yüksek.\nENGLISH DETAIL:\n- Error rate is 7%"
    tr, en = _parse_bilingual(text)
    assert "CDN hata" in tr
    assert "Error rate" in en


def test_parse_bilingual_rca():
    text = "TÜRKÇE ÖZET: Kök neden bulundu.\nROOT CAUSE: Connection pool exhaustion"
    tr, en = _parse_bilingual(text)
    assert "Kök neden" in tr
    assert "Connection pool" in en


def test_parse_bilingual_fallback():
    text = "Just plain English text"
    tr, en = _parse_bilingual(text)
    assert tr == ""
    assert "plain English" in en


def test_parse_bilingual_turkish_only():
    text = "TÜRKÇE ÖZET: Sadece Türkçe metin var."
    tr, en = _parse_bilingual(text)
    assert "Sadece Türkçe" in tr
