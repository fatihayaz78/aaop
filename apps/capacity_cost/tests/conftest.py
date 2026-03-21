"""Capacity & Cost test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.capacity_cost.config import CapacityCostConfig
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def capacity_config() -> CapacityCostConfig:
    return CapacityCostConfig()


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
    mock_response.content = [MagicMock(text="Capacity analysis: bandwidth trending up. Scale recommended.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.fetch_all = MagicMock(return_value=[])
    db.execute = MagicMock()
    return db


@pytest.fixture
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.get_json = AsyncMock(return_value=None)
    redis.set_json = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    return redis
