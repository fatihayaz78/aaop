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
    await _seed_admin_user(_sqlite)

    _duckdb = DuckDBClient(settings.duckdb_path)
    _duckdb.connect()
    _duckdb.init_tables()

    _redis = RedisClient(settings.redis_host, settings.redis_port)
    await _redis.connect()

    logger.info("all_clients_initialized")


async def _seed_admin_user(sqlite: SQLiteClient) -> None:
    """Insert default admin user, system tenant, and multi-tenant seed data."""
    import uuid

    import bcrypt

    # Seed multi-tenant hierarchy (idempotent)
    await _seed_tenant_hierarchy(sqlite)

    row = await sqlite.fetch_one("SELECT COUNT(*) as cnt FROM users")
    if row and row["cnt"] > 0:
        return

    # Ensure system tenant exists for FK
    existing = await sqlite.fetch_one("SELECT id FROM tenants WHERE id = 'system'")
    if not existing:
        await sqlite.execute(
            "INSERT INTO tenants (id, name, plan, sector) VALUES (?, ?, ?, ?)",
            ("system", "System", "enterprise", "platform"),
        )

    from shared.utils.settings import get_settings
    settings = get_settings()
    if settings.admin_password == "admin123":
        logger.warning("default_admin_password_in_use", msg="ADMIN_PASSWORD env var set edilmeli")
    password_hash = bcrypt.hashpw(settings.admin_password.encode(), bcrypt.gensalt()).decode()
    await sqlite.execute(
        "INSERT INTO users (id, tenant_id, username, password_hash, role, service_ids, active_service_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "ott_co", "admin", password_hash, "super_admin", '["sport_stream"]', "sport_stream"),
    )
    logger.info("seed_admin_user_created", username="admin")


async def _seed_tenant_hierarchy(sqlite: SQLiteClient) -> None:
    """Seed tenants and services (idempotent — INSERT OR IGNORE)."""
    tenants = [
        ("ott_co", "OTT Co", "enterprise", "ott"),
        ("tel_co", "Tel Co", "growth", "telekom"),
        ("airline_co", "Airline Co", "starter", "havayolu"),
    ]
    for tid, name, plan, sector in tenants:
        await sqlite.execute(
            "INSERT OR IGNORE INTO tenants (id, name, plan, sector) VALUES (?, ?, ?, ?)",
            (tid, name, plan, sector),
        )

    services = [
        ("sport_stream", "ott_co", "Sport Stream", "sport_stream"),
        ("tv_plus", "tel_co", "TV Plus", "tv_plus"),
        ("music_stream", "tel_co", "Music Stream", "music_stream"),
        ("fly_ent", "airline_co", "Fly Entertainment", "fly_ent"),
    ]
    for sid, tid, name, schema in services:
        await sqlite.execute(
            "INSERT OR IGNORE INTO services (id, tenant_id, name, duckdb_schema) VALUES (?, ?, ?, ?)",
            (sid, tid, name, schema),
        )

    # Migrate existing aaop_company users to ott_co
    await sqlite.execute(
        "UPDATE users SET tenant_id = 'ott_co', service_ids = '[\"sport_stream\"]', "
        "active_service_id = 'sport_stream' WHERE tenant_id = 'aaop_company'",
    )

    logger.info("tenant_hierarchy_seeded")


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
