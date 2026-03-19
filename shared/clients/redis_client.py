"""Async Redis wrapper. GCP migration: just change host to Memorystore."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)


class RedisClient:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        settings = get_settings()
        self._host = host or settings.redis_host
        self._port = port or settings.redis_port
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.Redis(
            host=self._host,
            port=self._port,
            decode_responses=True,
        )
        logger.info("redis_connected", host=self._host, port=self._port)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            msg = "RedisClient not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._client

    async def get(self, key: str) -> str | None:
        result = await self.client.get(key)
        return str(result) if result is not None else None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self.client.set(key, value, ex=ttl)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(value, default=str), ttl=ttl)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))
