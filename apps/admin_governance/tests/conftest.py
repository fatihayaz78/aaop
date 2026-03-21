"""Admin & Governance test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.admin_governance.config import AdminGovernanceConfig
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway


@pytest.fixture
def admin_config() -> AdminGovernanceConfig:
    return AdminGovernanceConfig()


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
    mock_response.content = [MagicMock(text="Admin operation completed successfully.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw


@pytest.fixture
def mock_sqlite() -> MagicMock:
    sqlite = MagicMock()
    sqlite.fetch_all = MagicMock(return_value=[])
    sqlite.execute = MagicMock()
    return sqlite


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.fetch_all = MagicMock(return_value=[])
    db.execute = MagicMock()
    return db
