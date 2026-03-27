"""Sync engine — orchestrates ingestion from source files to DuckDB cache.

Supports mtime-based upsert and post-import file deletion.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import date, datetime, timezone

import structlog

from shared.ingest.jsonl_parser import parse_json_file, parse_jsonl_gz, scan_source_directory
from shared.ingest.log_schemas import LOG_TABLE_SCHEMAS
from shared.ingest.source_config import SourceConfig, SyncResult

logger = structlog.get_logger(__name__)


class SyncEngine:
    def __init__(self, sqlite_client, logs_duckdb_client) -> None:
        self._sqlite = sqlite_client
        self._duckdb = logs_duckdb_client

    async def _get_ingestion_record(self, tenant_id: str, file_path: str) -> dict | None:
        row = await self._sqlite.fetch_one(
            "SELECT id, file_mtime FROM ingestion_log WHERE tenant_id = ? AND file_path = ?",
            (tenant_id, file_path),
        )
        return dict(row) if row else None

    async def _mark_ingested(self, tenant_id: str, source_name: str,
                             file_path: str, file_mtime: str, rows: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._sqlite.execute(
            """INSERT INTO ingestion_log (id, tenant_id, source_name, file_path, file_mtime, rows_ingested, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, file_path) DO UPDATE SET
                 file_mtime = excluded.file_mtime,
                 rows_ingested = excluded.rows_ingested,
                 ingested_at = excluded.ingested_at""",
            (str(uuid.uuid4()), tenant_id, source_name, file_path, file_mtime, rows, now),
        )

    @staticmethod
    def _get_file_mtime(file_path: str) -> str:
        try:
            return str(os.path.getmtime(file_path))
        except OSError:
            return ""

    @staticmethod
    def delete_source_file(file_path: str) -> bool:
        """Delete a source file after successful import. Never deletes directories."""
        try:
            if os.path.isfile(file_path):
                logger.info("deleting_source_file", file=file_path)
                os.remove(file_path)
                logger.info("source_file_deleted", file=file_path)
                return True
        except OSError as exc:
            logger.warning("source_file_delete_failed", file=file_path, error=str(exc))
        return False

    async def sync_source(
        self,
        tenant_id: str,
        source_config: SourceConfig,
        date_from: date | None = None,
        date_to: date | None = None,
        delete_after_import: bool = False,
    ) -> SyncResult:
        start_ms = time.time()
        errors: list[str] = []
        files_processed = 0
        total_rows = 0
        files_deleted = 0

        source_name = source_config.source_name

        # Ensure DuckDB schema and table
        self._duckdb.ensure_tenant_schema(tenant_id)
        create_sql = LOG_TABLE_SCHEMAS.get(source_name)
        if create_sql:
            self._duckdb.ensure_source_table(tenant_id, source_name, create_sql)

        # Scan files
        base_path = source_config.local_path or ""
        if not base_path:
            return SyncResult(
                source_name=source_name, files_processed=0, rows_inserted=0,
                rows_deleted_from_cache=0, files_deleted=0,
                errors=["No local_path configured"], duration_ms=0,
            )

        all_files = scan_source_directory(base_path, source_name)

        for fpath in all_files:
            current_mtime = self._get_file_mtime(fpath)

            # Check if already ingested with same mtime
            existing = await self._get_ingestion_record(tenant_id, fpath)
            if existing and existing.get("file_mtime") == current_mtime:
                continue  # skip unchanged file

            try:
                if fpath.endswith(".jsonl.gz") or fpath.endswith(".gz"):
                    records = parse_jsonl_gz(fpath, source_name, tenant_id)
                elif fpath.endswith(".json"):
                    records = parse_json_file(fpath, source_name, tenant_id)
                else:
                    continue

                if records:
                    rows = self._duckdb.insert_batch(tenant_id, source_name, records)
                    total_rows += rows
                    await self._mark_ingested(tenant_id, source_name, fpath, current_mtime, rows)

                files_processed += 1

                # Delete file after successful import if requested
                if delete_after_import and self.delete_source_file(fpath):
                    files_deleted += 1

            except Exception as exc:
                errors.append(f"{fpath}: {exc}")
                logger.warning("sync_file_error", file=fpath, error=str(exc))

        # Delete old records (>30 days)
        deleted = self._duckdb.delete_older_than(tenant_id, source_name, days=30)

        # Update source config
        now = datetime.now(timezone.utc).isoformat()
        error_str = "; ".join(errors) if errors else None
        await self._sqlite.execute(
            """UPDATE data_source_configs SET last_sync_at = ?, last_sync_rows = ?, last_sync_error = ?
               WHERE id = ?""",
            (now, total_rows, error_str, source_config.id),
        )

        elapsed = int((time.time() - start_ms) * 1000)
        logger.info(
            "sync_complete", source=source_name, files=files_processed,
            rows=total_rows, deleted_cache=deleted, deleted_files=files_deleted,
            elapsed_ms=elapsed,
        )

        return SyncResult(
            source_name=source_name,
            files_processed=files_processed,
            rows_inserted=total_rows,
            rows_deleted_from_cache=deleted,
            files_deleted=files_deleted,
            errors=errors,
            duration_ms=elapsed,
        )

    async def sync_all(self, tenant_id: str) -> list[SyncResult]:
        cursor = await self._sqlite.fetch_all(
            "SELECT * FROM data_source_configs WHERE tenant_id = ? AND enabled = 1",
            (tenant_id,),
        )
        results: list[SyncResult] = []
        for row in cursor:
            config = SourceConfig(**dict(row))
            result = await self.sync_source(tenant_id, config)
            results.append(result)
        return results
