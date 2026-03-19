"""Alert Center test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.alert_center.config import AlertCenterConfig
from apps.alert_center.tools import reset_storm_tracker
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def alert_config() -> AlertCenterConfig:
    return AlertCenterConfig()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture(autouse=True)
def _clean_storm():
    reset_storm_tracker()
    yield
    reset_storm_tracker()


@pytest.fixture
def mock_llm() -> LLMGateway:
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="[P1] CDN Error Rate Spike - Akamai edge error rate exceeded 5% threshold")]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 30
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.exists = AsyncMock(return_value=False)
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis
