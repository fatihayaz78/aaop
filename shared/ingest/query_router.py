"""Query router — routes to DuckDB (hot, ≤30 days) or source files (cold, >30 days)."""

from __future__ import annotations

from datetime import date, timedelta

import structlog

from shared.ingest.jsonl_parser import parse_json_file, parse_jsonl_gz, scan_source_directory

logger = structlog.get_logger(__name__)


class QueryRouter:
    def __init__(self, logs_duckdb_client, source_configs: dict[str, str] | None = None) -> None:
        self._duckdb = logs_duckdb_client
        self._source_paths = source_configs or {}

    def query(
        self,
        tenant_id: str,
        source_name: str,
        date_from: date,
        date_to: date,
        filters: dict | None = None,
        limit: int = 10000,
    ) -> tuple[list[dict], bool]:
        """Query data, returning (rows, from_cache).

        Hot path: date_from >= today - 30 days → DuckDB
        Cold path: date_from < today - 30 days → source files
        Mixed: union both.
        """
        today = date.today()
        hot_cutoff = today - timedelta(days=30)

        hot_results: list[dict] = []
        cold_results: list[dict] = []
        from_cache = True

        # Hot path: DuckDB
        if date_from >= hot_cutoff:
            hot_results = self._query_duckdb(tenant_id, source_name, date_from, date_to, filters, limit)
        elif date_to < hot_cutoff:
            # Entirely cold
            cold_results = self._query_source(tenant_id, source_name, date_from, date_to, limit)
            from_cache = False
        else:
            # Mixed: cold for old part, hot for recent part
            cold_results = self._query_source(tenant_id, source_name, date_from, hot_cutoff - timedelta(days=1), limit)
            hot_results = self._query_duckdb(tenant_id, source_name, hot_cutoff, date_to, filters, limit - len(cold_results))
            from_cache = False  # partial

        combined = cold_results + hot_results
        return combined[:limit], from_cache

    def _query_duckdb(
        self, tenant_id: str, source_name: str,
        date_from: date, date_to: date,
        filters: dict | None, limit: int,
    ) -> list[dict]:
        safe_tid = tenant_id.replace("-", "_").replace(" ", "_")
        table = f"{safe_tid}.{source_name}_logs"

        where_parts = [
            f"tenant_id = '{tenant_id}'",
            f"CAST(timestamp AS DATE) >= '{date_from.isoformat()}'",
            f"CAST(timestamp AS DATE) <= '{date_to.isoformat()}'",
        ]
        if filters:
            for k, v in filters.items():
                where_parts.append(f"{k} = '{v}'")

        sql = f"SELECT * FROM {table} WHERE {' AND '.join(where_parts)} LIMIT {limit}"

        try:
            return self._duckdb.query(tenant_id, sql)
        except Exception as exc:
            logger.warning("duckdb_query_error", error=str(exc))
            return []

    def _query_source(
        self, tenant_id: str, source_name: str,
        date_from: date, date_to: date, limit: int,
    ) -> list[dict]:
        """Fallback: read directly from source files."""
        base_path = self._source_paths.get(source_name, "")
        if not base_path:
            return []

        all_files = scan_source_directory(base_path, source_name)
        records: list[dict] = []

        for fpath in all_files:
            if len(records) >= limit:
                break
            if fpath.endswith(".jsonl.gz"):
                records.extend(parse_jsonl_gz(fpath, source_name, tenant_id))
            elif fpath.endswith(".json"):
                records.extend(parse_json_file(fpath, source_name, tenant_id))

        return records[:limit]
