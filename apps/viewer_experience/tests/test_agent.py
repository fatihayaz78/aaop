"""Tests for QoEAgent and ComplaintAgent."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.viewer_experience.agent import ComplaintAgent, QoEAgent, _parse_complaint_nlp
from shared.event_bus import EventBus, EventType
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── QoEAgent tests ──


@pytest.mark.asyncio
async def test_qoe_agent_degradation(mock_llm: LLMGateway, event_bus: EventBus):
    """Low QoE score should trigger degradation event."""
    agent = QoEAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "session": {
            "buffering_ratio": 0.20,
            "startup_time_ms": 5000,
            "bitrate_avg": 1000,
            "errors": ["err1"],
        },
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert result.get("error") is None
    assert result["output"]["action"] == "qoe_degradation"
    assert result["output"]["degradation_published"] is True
    assert result["output"]["quality_score"] < 2.5


@pytest.mark.asyncio
async def test_qoe_agent_normal(mock_llm: LLMGateway, event_bus: EventBus):
    """Good QoE score should not trigger degradation."""
    agent = QoEAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {
        "session": {"buffering_ratio": 0.0, "startup_time_ms": 1000, "bitrate_avg": 5000, "errors": []},
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result["output"]["action"] == "qoe_normal"
    assert result["output"]["quality_score"] == 5.0
    assert result["output"]["degradation_published"] is False


@pytest.mark.asyncio
async def test_qoe_agent_dedup(mock_llm: LLMGateway, event_bus: EventBus):
    """Same session within 5 min should be deduped."""
    agent = QoEAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    session = {"session_id": "fixed-session-001", "buffering_ratio": 0.1, "startup_time_ms": 3000, "bitrate_avg": 2000, "errors": []}

    await event_bus.start()
    # First run
    await agent.run(ctx, input_data={"session": session})
    # Second run — should dedup
    result = await agent.run(ctx, input_data={"session": session})
    await event_bus.stop()

    assert result["output"]["action"] == "dedup_skip"


@pytest.mark.asyncio
async def test_qoe_agent_no_session(mock_llm: LLMGateway, event_bus: EventBus):
    agent = QoEAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_session"


@pytest.mark.asyncio
async def test_qoe_publishes_degradation_event(mock_llm: LLMGateway, event_bus: EventBus):
    received: list[Any] = []

    async def handler(event: Any) -> None:
        received.append(event)

    event_bus.subscribe(EventType.QOE_DEGRADATION, handler)
    agent = QoEAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"session": {"buffering_ratio": 0.30, "startup_time_ms": 6000, "bitrate_avg": 500, "errors": ["e1"]}}

    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    await asyncio.sleep(0.2)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].event_type == "qoe_degradation"
    assert received[0].payload["quality_score"] < 2.5


# ── ComplaintAgent tests ──


@pytest.mark.asyncio
async def test_complaint_agent_categorize(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ComplaintAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"content": "Video keeps buffering, terrible experience", "source": "mobile_app"}

    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()

    assert result.get("error") is None
    assert result["output"]["category"] == "buffering"
    assert result["output"]["sentiment"] == "negative"
    assert result["output"]["priority"] in ("P0", "P1", "P2", "P3")
    assert result["output"]["complaint_id"].startswith("CMP-")


@pytest.mark.asyncio
async def test_complaint_agent_no_content(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ComplaintAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    result = await agent.run(ctx, input_data={})
    await event_bus.stop()

    assert result["output"]["action"] == "no_content"


# ── NLP parser tests ──


def test_parse_complaint_nlp_full():
    text = "CATEGORY: BUFFERING\nSENTIMENT: NEGATIVE\nPRIORITY: P2\nSUMMARY: Buffer issue"
    cat, sent, pri = _parse_complaint_nlp(text)
    assert cat == "buffering"
    assert sent == "negative"
    assert pri == "P2"


def test_parse_complaint_nlp_video():
    text = "CATEGORY: VIDEO_QUALITY\nSENTIMENT: VERY_NEGATIVE\nPRIORITY: P1"
    cat, sent, pri = _parse_complaint_nlp(text)
    assert cat == "video_quality"
    assert sent == "very_negative"
    assert pri == "P1"


def test_parse_complaint_nlp_fallback():
    text = "Some unstructured text"
    cat, sent, pri = _parse_complaint_nlp(text)
    assert cat == "other"
    assert sent == "neutral"
    assert pri == "P3"
