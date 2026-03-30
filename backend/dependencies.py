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
    """Seed multi-tenant hierarchy + demo users."""
    await _seed_tenant_hierarchy(sqlite)
    await _seed_demo_users(sqlite)


async def _seed_tenant_hierarchy(sqlite: SQLiteClient) -> None:
    """Seed tenants and services, clean up legacy records (idempotent)."""
    # Clean up old legacy tenants (S-MT-02) — delete referencing rows first
    for old_id in ("system", "s_sport_plus", "bein_sports", "tivibu", "aaop_company"):
        for child_table in ("users", "module_configs", "audit_log", "settings", "services"):
            try:
                await sqlite.execute(f"DELETE FROM {child_table} WHERE tenant_id = ?", (old_id,))
            except Exception:
                pass
        try:
            await sqlite.execute("DELETE FROM tenants WHERE id = ?", (old_id,))
        except Exception:
            pass

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

    logger.info("tenant_hierarchy_seeded")


async def _seed_demo_users(sqlite: SQLiteClient) -> None:
    """Seed demo users (idempotent — INSERT OR IGNORE by username)."""
    import uuid

    import bcrypt

    password_hash = bcrypt.hashpw(b"Captain2026!", bcrypt.gensalt()).decode()

    demo_users = [
        ("admin@captainlogar.demo", "ott_co",     "super_admin",  '["sport_stream","tv_plus","music_stream","fly_ent"]', "sport_stream"),
        ("admin@ottco.demo",        "ott_co",     "tenant_admin", '["sport_stream"]',                                    "sport_stream"),
        ("admin@telco.demo",        "tel_co",     "tenant_admin", '["tv_plus","music_stream"]',                          "tv_plus"),
        ("user@telco.demo",         "tel_co",     "service_user", '["tv_plus"]',                                         "tv_plus"),
        ("admin@airlineco.demo",    "airline_co", "tenant_admin", '["fly_ent"]',                                         "fly_ent"),
    ]

    for email, tenant_id, role, service_ids, active_service in demo_users:
        existing = await sqlite.fetch_one("SELECT id FROM users WHERE username = ?", (email,))
        if not existing:
            await sqlite.execute(
                "INSERT INTO users (id, tenant_id, username, password_hash, role, service_ids, active_service_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), tenant_id, email, password_hash, role, service_ids, active_service),
            )

    logger.info("demo_users_seeded")


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
