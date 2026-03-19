"""Tests for backend/dependencies.py — DI helpers and tenant context."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.dependencies import (
    get_duckdb,
    get_redis,
    get_sqlite,
    get_tenant_context,
    init_clients,
    shutdown_clients,
)
from shared.schemas.base_event import TenantContext


def test_get_tenant_context():
    ctx = get_tenant_context(x_tenant_id="bein_sports", x_user_id="u1", x_role="admin")
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == "bein_sports"
    assert ctx.user_id == "u1"
    assert ctx.role == "admin"


def test_get_tenant_context_minimal():
    ctx = get_tenant_context(x_tenant_id="test", x_user_id=None, x_role=None)
    assert ctx.tenant_id == "test"
    assert ctx.user_id is None


def test_get_sqlite_not_initialized():
    import backend.dependencies as deps

    original = deps._sqlite
    deps._sqlite = None
    with pytest.raises(RuntimeError, match="not initialized"):
        get_sqlite()
    deps._sqlite = original


def test_get_duckdb_not_initialized():
    import backend.dependencies as deps

    original = deps._duckdb
    deps._duckdb = None
    with pytest.raises(RuntimeError, match="not initialized"):
        get_duckdb()
    deps._duckdb = original


def test_get_redis_not_initialized():
    import backend.dependencies as deps

    original = deps._redis
    deps._redis = None
    with pytest.raises(RuntimeError, match="not initialized"):
        get_redis()
    deps._redis = original


@pytest.mark.asyncio
async def test_init_and_shutdown_clients(tmp_path):
    from shared.utils.settings import Settings

    test_settings = Settings(
        anthropic_api_key="test",
        sqlite_path=str(tmp_path / "test.db"),
        duckdb_path=str(tmp_path / "test.duckdb"),
        redis_host="localhost",
        redis_port=6379,
    )
    with (
        patch("backend.dependencies.get_settings", return_value=test_settings),
        patch("backend.dependencies.RedisClient") as mock_redis_cls,
    ):
        mock_redis_instance = AsyncMock()
        mock_redis_cls.return_value = mock_redis_instance

        await init_clients()

        # Verify clients are set
        assert get_sqlite() is not None
        assert get_duckdb() is not None

        await shutdown_clients()
