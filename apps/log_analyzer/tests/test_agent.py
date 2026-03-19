"""Tests for LogAnalyzerAgent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.log_analyzer.agent import LogAnalyzerAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


@pytest.fixture
def mock_llm() -> LLMGateway:
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="CDN analysis complete. Error rate normal.")]
    mock_response.usage.input_tokens = 200
    mock_response.usage.output_tokens = 100
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.mark.asyncio
async def test_agent_run_no_data(mock_llm: LLMGateway, event_bus: EventBus):
    agent = LogAnalyzerAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    await event_bus.start()
    result = await agent.run(ctx)
    await event_bus.stop()
    assert result["error"] is None
    assert result["llm_response"]["action"] == "no_data"


@pytest.mark.asyncio
async def test_agent_run_with_metrics(mock_llm: LLMGateway, event_bus: EventBus):
    agent = LogAnalyzerAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    input_data = {
        "metrics": {
            "total_requests": 1000,
            "error_rate": 0.08,
            "cache_hit_rate": 0.45,
        },
        "anomalies": [{"anomaly_type": "high_error_rate", "severity": "P1", "value": 0.08, "threshold": 0.05, "description": "High errors"}],
        "period_start": "2026-03-19T00:00:00",
        "period_end": "2026-03-19T06:00:00",
    }
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["error"] is None
    assert result["decision"]["anomaly_count"] == 1


@pytest.mark.asyncio
async def test_agent_app_name(mock_llm: LLMGateway, event_bus: EventBus):
    agent = LogAnalyzerAgent(llm_gateway=mock_llm, event_bus=event_bus)
    assert agent.app_name == "log_analyzer"


@pytest.mark.asyncio
async def test_agent_publishes_events(mock_llm: LLMGateway, event_bus: EventBus):
    received: list[Any] = []

    async def handler(event: Any) -> None:
        received.append(event)

    from shared.event_bus import EventType

    event_bus.subscribe(EventType.ANALYSIS_COMPLETE, handler)
    event_bus.subscribe(EventType.CDN_ANOMALY_DETECTED, handler)

    agent = LogAnalyzerAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="test_tenant")
    input_data = {
        "metrics": {"total_requests": 100, "error_rate": 0.1},
        "anomalies": [{"anomaly_type": "high_error_rate", "severity": "P1", "value": 0.1, "threshold": 0.05, "description": "test"}],
    }
    await event_bus.start()
    await agent.run(ctx, input_data=input_data)
    import asyncio
    await asyncio.sleep(0.2)
    await event_bus.stop()

    event_types = [e.event_type for e in received]
    assert "analysis_complete" in event_types
    assert "cdn_anomaly_detected" in event_types
