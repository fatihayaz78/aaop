"""FastAPI dependency injection — DB sessions, tenant context."""

from __future__ import annotations

import structlog
from fastapi import Header, HTTPException, status

from shared.clients.duckdb_client import DuckDBClient
from shared.clients.redis_client import RedisClient
from shared.clients.sqlite_client import SQLiteClient
from shared.schemas.base_event import TenantContext
from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)

# Singleton clients (initialized at startup)
_sqlite: SQLiteClient | None = None
_duckdb: DuckDBClient | None = None
_redis: RedisClient | None = None


async def init_clients() -> None:
    """Initialize all DB clients. Called from FastAPI startup event."""
    global _sqlite, _duckdb, _redis
    settings = get_settings()

    _sqlite = SQLiteClient(settings.sqlite_path)
    await _sqlite.connect()
    await _sqlite.init_tables()

    _duckdb = DuckDBClient(settings.duckdb_path)
    _duckdb.connect()
    _duckdb.init_tables()

    _redis = RedisClient(settings.redis_host, settings.redis_port)
    await _redis.connect()

    logger.info("all_clients_initialized")


async def shutdown_clients() -> None:
    """Disconnect all DB clients. Called from FastAPI shutdown event."""
    if _sqlite:
        await _sqlite.disconnect()
    if _duckdb:
        _duckdb.disconnect()
    if _redis:
        await _redis.disconnect()
    logger.info("all_clients_disconnected")


def get_sqlite() -> SQLiteClient:
    if _sqlite is None:
        msg = "SQLiteClient not initialized"
        raise RuntimeError(msg)
    return _sqlite


def get_duckdb() -> DuckDBClient:
    if _duckdb is None:
        msg = "DuckDBClient not initialized"
        raise RuntimeError(msg)
    return _duckdb


def get_redis() -> RedisClient:
    if _redis is None:
        msg = "RedisClient not initialized"
        raise RuntimeError(msg)
    return _redis


def get_tenant_context(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    x_role: str | None = Header(None, alias="X-Role"),
) -> TenantContext:
    """Extract tenant context from request headers."""
    if not x_tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Tenant-ID header required")
    return TenantContext(tenant_id=x_tenant_id, user_id=x_user_id, role=x_role)
