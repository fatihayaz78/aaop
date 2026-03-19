"""Ops Center test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.ops_center.config import OpsCenterConfig
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def ops_config() -> OpsCenterConfig:
    return OpsCenterConfig()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def mock_llm() -> LLMGateway:
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=(
        "1. TÜRKÇE ÖZET: CDN hata oranı %7'ye yükseldi. Akamai edge sunucularında bağlantı hatası tespit edildi.\n"
        "2. ENGLISH DETAIL:\n"
        "- Error rate spiked to 7% on Akamai edge servers\n"
        "- ERR_CONNECT_FAIL is the primary error code\n"
        "- Affected services: CDN, player\n"
        "3. SEVERITY ASSESSMENT: P1\n"
        "4. RECOMMENDED ACTIONS:\n"
        "1. Check Akamai origin health\n"
        "2. Monitor error rate trend\n"
    ))]
    mock_response.usage.input_tokens = 300
    mock_response.usage.output_tokens = 150
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def mock_llm_rca() -> LLMGateway:
    """LLM mock for RCA that returns Opus-style response."""
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=(
        "1. TÜRKÇE ÖZET: Kök neden Akamai origin sunucusundaki bağlantı zaman aşımıdır.\n"
        "2. ROOT CAUSE: Origin server connection pool exhaustion caused cascading failures.\n"
        "3. CONTRIBUTING FACTORS:\n"
        "- High traffic from live event\n"
        "- Connection pool max reached\n"
        "4. TIMELINE:\n"
        "- 14:00 Traffic ramp-up\n"
        "- 14:15 Connection pool saturated\n"
        "- 14:20 Error rate exceeded 5%\n"
        "5. RECOMMENDATIONS:\n"
        "- Increase connection pool size\n"
        "- Add circuit breaker\n"
        "6. CONFIDENCE: 0.85\n"
    ))]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 250
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw
