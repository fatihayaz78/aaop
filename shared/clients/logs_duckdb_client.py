"""DuckDB client for logs.duckdb — hot cache for ingested log data (≤30 days)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import structlog

logger = structlog.get_logger(__name__)

LOGS_DUCKDB_PATH = os.environ.get("LOGS_DUCKDB_PATH", "./data/duckdb/logs.duckdb")


class LogsDuckDBClient:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or LOGS_DUCKDB_PATH
        self._conn: duckdb.DuckDBPyConnection | None = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = duckdb.connect(self._db_path)
            logger.info("logs_duckdb_connected", path=self._db_path)
        return self._conn

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def ensure_tenant_schema(self, tenant_id: str) -> None:
        conn = self.get_connection()
        safe_id = tenant_id.replace("-", "_").replace(" ", "_")
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {safe_id}")
        logger.info("tenant_schema_ensured", tenant_id=safe_id)

    def ensure_source_table(self, tenant_id: str, source: str, create_sql: str) -> None:
        conn = self.get_connection()
        safe_tid = tenant_id.replace("-", "_").replace(" ", "_")
        table_name = f"{safe_tid}.{source}_logs"
        full_sql = create_sql.replace("{TABLE_NAME}", table_name)
        conn.execute(full_sql)
        logger.info("source_table_ensured", table=table_name)

    def query(self, tenant_id: str, sql: str, params: list[Any] | None = None) -> list[dict]:
        conn = self.get_connection()
        rel = conn.execute(sql, params) if params else conn.execute(sql)
        columns = [desc[0] for desc in rel.description]
        rows = rel.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def insert_batch(self, tenant_id: str, source: str, records: list[dict]) -> int:
        if not records:
            return 0
        conn = self.get_connection()
        safe_tid = tenant_id.replace("-", "_").replace(" ", "_")
        table_name = f"{safe_tid}.{source}_logs"

        columns = list(records[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)
        sql = f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"

        for rec in records:
            vals = [rec.get(c) for c in columns]
            conn.execute(sql, vals)

        return len(records)

    def delete_older_than(self, tenant_id: str, source: str, days: int = 30) -> int:
        conn = self.get_connection()
        safe_tid = tenant_id.replace("-", "_").replace(" ", "_")
        table_name = f"{safe_tid}.{source}_logs"

        count_sql = f"SELECT COUNT(*) as cnt FROM {table_name} WHERE ingested_at < NOW() - INTERVAL '{days} days'"
        try:
            result = conn.execute(count_sql).fetchone()
            count = result[0] if result else 0
        except Exception:
            return 0

        if count > 0:
            conn.execute(f"DELETE FROM {table_name} WHERE ingested_at < NOW() - INTERVAL '{days} days'")
            logger.info("deleted_old_records", table=table_name, count=count, days=days)

        return count
