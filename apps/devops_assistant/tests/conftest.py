"""DevOps Assistant test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.devops_assistant.config import DevOpsAssistantConfig
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def devops_config() -> DevOpsAssistantConfig:
    return DevOpsAssistantConfig()


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
    mock_response.content = [MagicMock(text="Service diagnostics: All services healthy.")]
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
def mock_chroma() -> MagicMock:
    chroma = MagicMock()
    chroma.query = MagicMock(return_value={
        "documents": [["Step 1: Check logs. Step 2: Restart."]],
        "ids": [["rb-1"]],
        "metadatas": [[{"tenant_id": "t1", "title": "CDN Restart Runbook"}]],
    })
    return chroma
