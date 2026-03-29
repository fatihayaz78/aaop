"""Async SQLite wrapper. GCP migration: swap to Cloud Spanner adaptor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)


class SQLiteClient:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or get_settings().sqlite_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        logger.info("sqlite_connected", path=self._db_path)

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("sqlite_disconnected")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            msg = "SQLiteClient not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows] if rows else []  # type: ignore[arg-type]

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def init_tables(self) -> None:
        """Create platform metadata tables if they don't exist."""
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                plan        TEXT NOT NULL DEFAULT 'starter',
                sector      TEXT NOT NULL DEFAULT 'ott',
                timezone    TEXT DEFAULT 'Europe/Istanbul',
                status      TEXT NOT NULL DEFAULT 'active',
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                tenant_id   TEXT NOT NULL REFERENCES tenants(id),
                username    TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role        TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1,
                last_login  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS module_configs (
                id          TEXT PRIMARY KEY,
                tenant_id   TEXT NOT NULL REFERENCES tenants(id),
                module_name TEXT NOT NULL,
                is_enabled  INTEGER DEFAULT 1,
                config_json TEXT,
                updated_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(tenant_id, module_name)
            );

            CREATE TABLE IF NOT EXISTS services (
                id              TEXT PRIMARY KEY,
                tenant_id       TEXT NOT NULL REFERENCES tenants(id),
                name            TEXT NOT NULL,
                duckdb_schema   TEXT NOT NULL,
                sector_override TEXT,
                status          TEXT NOT NULL DEFAULT 'active',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          TEXT PRIMARY KEY,
                tenant_id   TEXT NOT NULL,
                user_id     TEXT,
                action      TEXT NOT NULL,
                resource    TEXT,
                detail_json TEXT,
                ip_hash     TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                id TEXT PRIMARY KEY DEFAULT 'global',
                tenant_id TEXT NOT NULL,
                aws_access_key_id TEXT,
                aws_secret_access_key TEXT,
                aws_region TEXT DEFAULT 'eu-central-1',
                s3_bucket TEXT,
                s3_prefix TEXT DEFAULT 'logs/',
                gcp_project_id TEXT,
                gcp_dataset_id TEXT,
                gcp_credentials_json TEXT,
                bigquery_enabled INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        await self.conn.commit()

        # Migration: add columns if missing (SQLite has no ADD COLUMN IF NOT EXISTS)
        await self._migrate_columns()

        logger.info("sqlite_tables_initialized")

    async def _migrate_columns(self) -> None:
        """Add columns introduced in S-MT-01 if they don't exist yet."""
        # SQLite ALTER TABLE ADD COLUMN requires constant defaults only
        for table, column, default in [
            ("tenants", "sector", "'ott'"),
            ("tenants", "status", "'active'"),
            ("tenants", "updated_at", "NULL"),
            ("users", "service_ids", "'[]'"),
            ("users", "active_service_id", "NULL"),
        ]:
            try:
                await self.conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
            except Exception:
                try:
                    await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT {default}")
                    logger.info("sqlite_column_added", table=table, column=column)
                except Exception as alter_err:
                    logger.debug("sqlite_column_add_skipped", table=table, column=column, error=str(alter_err))
        await self.conn.commit()
