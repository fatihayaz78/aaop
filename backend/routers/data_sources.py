"""Data Sources API — source config CRUD, sync triggers, query routing."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import aiosqlite
import structlog
from fastapi import APIRouter

from shared.clients.logs_duckdb_client import LogsDuckDBClient
from shared.ingest.source_config import (
    INGESTION_LOG_TABLE_SQL,
    SOURCE_CONFIG_TABLE_SQL,
    SourceConfig,
    SourceConfigCreate,
    SyncResult,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/data-sources", tags=["data-sources"])

_DB_PATH = "data/sqlite/platform.db"
_logs_duckdb = LogsDuckDBClient()


async def _get_db():
    import os
    os.makedirs("data/sqlite", exist_ok=True)
    db = await aiosqlite.connect(_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute(SOURCE_CONFIG_TABLE_SQL)
    await db.execute(INGESTION_LOG_TABLE_SQL)
    # Migration guard — add file_mtime if missing
    try:
        cursor = await db.execute("PRAGMA table_info(ingestion_log)")
        cols = [r[1] for r in await cursor.fetchall()]
        if "file_mtime" not in cols:
            await db.execute("ALTER TABLE ingestion_log ADD COLUMN file_mtime TEXT")
    except Exception:
        pass
    await db.commit()
    return db


# ── CRUD ──


@router.get("/configs")
async def list_configs(tenant_id: str = "aaop_company") -> list[dict]:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM data_source_configs WHERE tenant_id = ? ORDER BY source_name",
            (tenant_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("/configs")
async def create_config(req: SourceConfigCreate) -> dict:
    config_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO data_source_configs
               (id, tenant_id, source_name, source_type, local_path, s3_bucket, s3_prefix,
                enabled, sync_interval_minutes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (config_id, req.tenant_id, req.source_name, req.source_type,
             req.local_path, req.s3_bucket, req.s3_prefix,
             1 if req.enabled else 0, req.sync_interval_minutes, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM data_source_configs WHERE id = ?", (config_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {"id": config_id}
    finally:
        await db.close()


@router.patch("/configs/{config_id}")
async def update_config(config_id: str, body: dict) -> dict:
    db = await _get_db()
    try:
        allowed = {"local_path", "s3_bucket", "s3_prefix", "enabled", "sync_interval_minutes", "source_type"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if "enabled" in updates:
            updates["enabled"] = 1 if updates["enabled"] else 0
        for key, val in updates.items():
            await db.execute(f"UPDATE data_source_configs SET {key} = ? WHERE id = ?", (val, config_id))
        await db.commit()
        cursor = await db.execute("SELECT * FROM data_source_configs WHERE id = ?", (config_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {"error": "not found"}
    finally:
        await db.close()


@router.delete("/configs/{config_id}")
async def delete_config(config_id: str) -> dict:
    db = await _get_db()
    try:
        await db.execute("DELETE FROM data_source_configs WHERE id = ?", (config_id,))
        await db.commit()
        return {"deleted": config_id}
    finally:
        await db.close()


# ── SYNC ──


class _SimpleSQLite:
    """Minimal async SQLite wrapper for SyncEngine compatibility."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path

    async def _ensure_tables(self, db) -> None:
        await db.execute(SOURCE_CONFIG_TABLE_SQL)
        await db.execute(INGESTION_LOG_TABLE_SQL)
        try:
            cursor = await db.execute("PRAGMA table_info(ingestion_log)")
            cols = [r[1] for r in await cursor.fetchall()]
            if "file_mtime" not in cols:
                await db.execute("ALTER TABLE ingestion_log ADD COLUMN file_mtime TEXT")
        except Exception:
            pass
        await db.commit()

    async def fetch_one(self, sql: str, params=None):
        import os
        os.makedirs("data/sqlite", exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            await self._ensure_tables(db)
            cursor = await db.execute(sql, params or ())
            return await cursor.fetchone()

    async def fetch_all(self, sql: str, params=None):
        import os
        os.makedirs("data/sqlite", exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            await self._ensure_tables(db)
            cursor = await db.execute(sql, params or ())
            return await cursor.fetchall()

    async def execute(self, sql: str, params=None):
        import os
        os.makedirs("data/sqlite", exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await self._ensure_tables(db)
            await db.execute(sql, params or ())
            await db.commit()


_sqlite_helper = _SimpleSQLite(_DB_PATH)


@router.post("/sync/{config_id}")
async def sync_single(config_id: str) -> dict:
    from shared.ingest.sync_engine import SyncEngine

    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM data_source_configs WHERE id = ?", (config_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "Config not found"}
        config = SourceConfig(**{
            **dict(row),
            "enabled": bool(row["enabled"]),
        })
    finally:
        await db.close()

    try:
        engine = SyncEngine(_sqlite_helper, _logs_duckdb)
        result = await engine.sync_source(config.tenant_id, config)
        return result.model_dump()
    except Exception as exc:
        logger.warning("sync_error", config_id=config_id, error=str(exc))
        return SyncResult(
            source_name=config.source_name, files_processed=0, rows_inserted=0,
            rows_deleted_from_cache=0, errors=[str(exc)], duration_ms=0,
        ).model_dump()


@router.post("/sync-all")
async def sync_all(tenant_id: str = "aaop_company") -> list[dict]:
    from shared.ingest.sync_engine import SyncEngine

    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM data_source_configs WHERE tenant_id = ? AND enabled = 1",
            (tenant_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    results: list[dict] = []
    for row in rows:
        config = SourceConfig(**{**dict(row), "enabled": bool(row["enabled"])})
        try:
            engine = SyncEngine(_sqlite_helper, _logs_duckdb)
            result = await engine.sync_source(tenant_id, config)
            results.append(result.model_dump())
        except Exception as exc:
            logger.warning("sync_all_error", source=config.source_name, error=str(exc))
            results.append(SyncResult(
                source_name=config.source_name, files_processed=0, rows_inserted=0,
                rows_deleted_from_cache=0, errors=[str(exc)], duration_ms=0,
            ).model_dump())
    return results


# ── STATUS ──


@router.get("/sync-status")
async def sync_status(tenant_id: str = "aaop_company") -> list[dict]:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM data_source_configs WHERE tenant_id = ? ORDER BY source_name",
            (tenant_id,),
        )
        rows = await cursor.fetchall()
        statuses = []
        for row in rows:
            statuses.append({
                "source_name": row["source_name"],
                "source_type": row["source_type"],
                "last_sync_at": row["last_sync_at"],
                "last_sync_rows": row["last_sync_rows"],
                "last_sync_error": row["last_sync_error"],
                "enabled": bool(row["enabled"]),
            })
        return statuses
    finally:
        await db.close()


# ── QUERY ──


@router.get("/query/{source_name}")
async def query_source(
    source_name: str,
    tenant_id: str = "aaop_company",
    date_from: str = "2026-03-01",
    date_to: str = "2026-03-31",
    limit: int = 1000,
) -> dict:
    from shared.ingest.query_router import QueryRouter

    # Get source path
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT local_path FROM data_source_configs WHERE tenant_id = ? AND source_name = ?",
            (tenant_id, source_name),
        )
        row = await cursor.fetchone()
        source_path = row["local_path"] if row else None
    finally:
        await db.close()

    source_paths = {source_name: source_path} if source_path else {}
    qr = QueryRouter(_logs_duckdb, source_paths)

    df = date.fromisoformat(date_from)
    dt = date.fromisoformat(date_to)
    rows, from_cache = qr.query(tenant_id, source_name, df, dt, limit=limit)

    return {
        "source": source_name,
        "rows": len(rows),
        "data": rows[:limit],
        "from_cache": from_cache,
    }


# ── IMPORT-DELETE + WATCH STATUS ──


@router.post("/import-delete/{config_id}")
async def import_and_delete(config_id: str) -> dict:
    """Sync source + delete imported files."""
    from shared.ingest.sync_engine import SyncEngine

    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM data_source_configs WHERE id = ?", (config_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "Config not found"}
        config = SourceConfig(**{**dict(row), "enabled": bool(row["enabled"])})
    finally:
        await db.close()

    try:
        engine = SyncEngine(_sqlite_helper, _logs_duckdb)
        result = await engine.sync_source(config.tenant_id, config, delete_after_import=True)
        return result.model_dump()
    except Exception as exc:
        logger.warning("import_delete_error", config_id=config_id, error=str(exc))
        return SyncResult(
            source_name=config.source_name, files_processed=0, rows_inserted=0,
            rows_deleted_from_cache=0, files_deleted=0, errors=[str(exc)], duration_ms=0,
        ).model_dump()


@router.get("/watch-status")
async def watch_status(tenant_id: str = "aaop_company") -> dict:
    """Return watcher status and pending file counts per folder."""
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest

    # Try to get watcher from app state
    from backend.main import app
    watcher = getattr(app.state, "watcher", None)
    watching = watcher.is_active if watcher else False

    folders = []
    if watcher:
        folders = watcher.get_folder_status()
    else:
        # Fallback: check folders manually
        import os
        from shared.ingest.default_configs import BASE_MOCK_DATA_PATH
        from shared.ingest.source_config import FOLDER_TO_SOURCE
        tenant_path = os.path.join(BASE_MOCK_DATA_PATH, tenant_id)
        for folder_name, source_name in FOLDER_TO_SOURCE.items():
            folder_path = os.path.join(tenant_path, folder_name)
            exists = os.path.isdir(folder_path)
            file_count = 0
            if exists:
                for _root, _dirs, files in os.walk(folder_path):
                    file_count += sum(1 for f in files if f.endswith((".jsonl.gz", ".json", ".gz")))
            folders.append({"folder": folder_name, "source_name": source_name, "exists": exists, "file_count": file_count})

    return {"watching": watching, "folders": folders}
