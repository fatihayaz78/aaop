"""Viewer Experience test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.viewer_experience.config import ViewerExperienceConfig
from apps.viewer_experience.tools import reset_session_dedup
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def viewer_config() -> ViewerExperienceConfig:
    return ViewerExperienceConfig()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture(autouse=True)
def _clean_dedup():
    reset_session_dedup()
    yield
    reset_session_dedup()


@pytest.fixture
def mock_llm() -> LLMGateway:
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = None
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=(
        "QoE degradation detected. High buffering ratio affecting viewer experience.\n"
        "CATEGORY: BUFFERING\n"
        "SENTIMENT: NEGATIVE\n"
        "PRIORITY: P2\n"
        "SUMMARY: Viewer experiencing frequent buffering"
    ))]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 60
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw
