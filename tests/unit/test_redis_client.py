"""Tests for shared/clients/redis_client.py (mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from shared.clients.redis_client import RedisClient


@pytest.mark.asyncio
async def test_get_returns_none(mock_redis: RedisClient):
    result = await mock_redis.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_json(mock_redis: RedisClient):
    mock_redis._client.get.return_value = '{"key": "value"}'
    result = await mock_redis.get_json("test_key")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_set_calls_redis(mock_redis: RedisClient):
    await mock_redis.set("k", "v", ttl=60)
    mock_redis._client.set.assert_called_once_with("k", "v", ex=60)


@pytest.mark.asyncio
async def test_delete(mock_redis: RedisClient):
    await mock_redis.delete("k")
    mock_redis._client.delete.assert_called_once_with("k")


@pytest.mark.asyncio
async def test_exists(mock_redis: RedisClient):
    result = await mock_redis.exists("k")
    assert result is False


@pytest.mark.asyncio
async def test_set_json(mock_redis: RedisClient):
    await mock_redis.set_json("k", {"a": 1}, ttl=300)
    mock_redis._client.set.assert_called_once()


@pytest.mark.asyncio
async def test_get_json_returns_none(mock_redis: RedisClient):
    mock_redis._client.get.return_value = None
    result = await mock_redis.get_json("missing")
    assert result is None


def test_constructor_with_params():
    client = RedisClient(host="redis.example.com", port=6380)
    assert client._host == "redis.example.com"
    assert client._port == 6380


@pytest.mark.asyncio
async def test_connect_and_disconnect():
    client = RedisClient(host="localhost", port=6379)
    with patch("shared.clients.redis_client.aioredis.Redis") as mock_redis_cls:
        mock_instance = AsyncMock()
        mock_redis_cls.return_value = mock_instance
        await client.connect()
        assert client._client is not None
        await client.disconnect()
        assert client._client is None


@pytest.mark.asyncio
async def test_disconnect_noop_when_not_connected():
    client = RedisClient(host="localhost", port=6379)
    client._client = None
    await client.disconnect()  # Should not raise


def test_not_connected_raises():
    client = RedisClient.__new__(RedisClient)
    client._client = None
    with pytest.raises(RuntimeError, match="not connected"):
        _ = client.client
