"""Shared test fixtures — mock tenant, mock LLM, temp DB paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.clients.duckdb_client import DuckDBClient
from shared.clients.redis_client import RedisClient
from shared.clients.sqlite_client import SQLiteClient
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext


@pytest.fixture
def tenant_context() -> TenantContext:
    return TenantContext(tenant_id="test_tenant", user_id="user_001", role="admin")


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sqlite_path(tmp_dir: Path) -> str:
    return str(tmp_dir / "test_platform.db")


@pytest.fixture
def duckdb_path(tmp_dir: Path) -> str:
    return str(tmp_dir / "test_analytics.duckdb")


@pytest.fixture
def chroma_path(tmp_dir: Path) -> str:
    return str(tmp_dir / "test_chromadb")


@pytest.fixture
async def sqlite_client(sqlite_path: str) -> SQLiteClient:
    client = SQLiteClient(db_path=sqlite_path)
    await client.connect()
    await client.init_tables()
    yield client
    await client.disconnect()


@pytest.fixture
def duckdb_client(duckdb_path: str) -> DuckDBClient:
    client = DuckDBClient(db_path=duckdb_path)
    client.connect()
    client.init_tables()
    yield client
    client.disconnect()


@pytest.fixture
def mock_redis() -> RedisClient:
    """Return a RedisClient with a mocked internal client (no actual Redis needed)."""
    rc = RedisClient.__new__(RedisClient)
    rc._host = "localhost"
    rc._port = 6379
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.exists = AsyncMock(return_value=False)
    mock_client.aclose = AsyncMock()
    rc._client = mock_client
    return rc


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def mock_llm_gateway(mock_redis: RedisClient) -> LLMGateway:
    """LLMGateway with mocked Anthropic client."""
    gw = LLMGateway.__new__(LLMGateway)
    gw._redis = mock_redis
    gw._total_input_tokens = 0
    gw._total_output_tokens = 0
    mock_anthropic = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mock LLM response")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.stop_reason = "end_turn"
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    gw._anthropic = mock_anthropic
    return gw
