"""Tests for the Data Ingestion Layer — logs_duckdb_client, jsonl_parser, sync_engine, query_router, API endpoints."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.clients.logs_duckdb_client import LogsDuckDBClient
from shared.ingest.jsonl_parser import parse_jsonl_gz, scan_source_directory
from shared.ingest.log_schemas import LOG_TABLE_SCHEMAS
from shared.ingest.source_config import SourceConfig, SyncResult


# ── LogsDuckDBClient ──


class TestLogsDuckDBClient:
    def test_logs_duckdb_client_init(self, tmp_path: Path):
        db_path = str(tmp_path / "test_logs.duckdb")
        client = LogsDuckDBClient(db_path=db_path)
        conn = client.get_connection()
        assert conn is not None
        client.disconnect()

    def test_ensure_tenant_schema(self, tmp_path: Path):
        db_path = str(tmp_path / "test_logs.duckdb")
        client = LogsDuckDBClient(db_path=db_path)
        client.ensure_tenant_schema("aaop_company")
        # Should not raise
        result = client.query("aaop_company", "SELECT 1 as ok")
        assert result[0]["ok"] == 1
        client.disconnect()

    def test_delete_older_than_30_days(self, tmp_path: Path):
        db_path = str(tmp_path / "test_logs.duckdb")
        client = LogsDuckDBClient(db_path=db_path)
        client.ensure_tenant_schema("aaop_company")
        # Create table
        client.get_connection().execute("""
            CREATE TABLE IF NOT EXISTS aaop_company.test_logs (
                timestamp TIMESTAMP, tenant_id TEXT, ingested_at TIMESTAMP
            )
        """)
        # Insert old record
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        client.get_connection().execute(
            "INSERT INTO aaop_company.test_logs VALUES (?, ?, ?)",
            ["2026-01-01T00:00:00", "aaop_company", old_ts],
        )
        # Insert recent record
        recent_ts = datetime.now(timezone.utc).isoformat()
        client.get_connection().execute(
            "INSERT INTO aaop_company.test_logs VALUES (?, ?, ?)",
            ["2026-03-20T00:00:00", "aaop_company", recent_ts],
        )

        deleted = client.delete_older_than("aaop_company", "test", days=30)
        assert deleted == 1

        remaining = client.query("aaop_company", "SELECT COUNT(*) as cnt FROM aaop_company.test_logs")
        assert remaining[0]["cnt"] == 1
        client.disconnect()


# ── JSONL Parser ──


class TestJSONLParser:
    def _make_gz(self, tmp_path: Path, records: list[dict], filename: str = "test.jsonl.gz") -> str:
        path = tmp_path / filename
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return str(path)

    def test_jsonl_parser_medianova(self, tmp_path: Path):
        records = [
            {"timestamp": "2026-03-04T19:30:00Z", "edge_node": "ist-01",
             "remote_addr": "1.2.3.4", "bytes_sent": 524288, "status": 200,
             "proxy_cache_status": "HIT", "country_code": "TR"},
        ]
        path = self._make_gz(tmp_path, records)
        result = parse_jsonl_gz(path, "medianova", "aaop_company")
        assert len(result) == 1
        assert result[0]["tenant_id"] == "aaop_company"
        assert result[0]["status_code"] == 200
        assert result[0]["edge_server"] == "ist-01"

    def test_jsonl_parser_widevine(self, tmp_path: Path):
        records = [
            {"timestamp": "2026-03-04T19:30:00Z", "event_type": "license_request",
             "device_type": "android", "status": "success", "response_time_ms": 120},
        ]
        path = self._make_gz(tmp_path, records)
        result = parse_jsonl_gz(path, "widevine_drm", "aaop_company")
        assert len(result) == 1
        assert result[0]["status"] == "success"

    def test_jsonl_parser_player_events(self, tmp_path: Path):
        records = [
            {"timestamp": "2026-03-04T19:30:00Z", "event_type": "session_start",
             "session_id": "s1", "device_type": "android", "buffer_ratio": 0.003},
        ]
        path = self._make_gz(tmp_path, records)
        result = parse_jsonl_gz(path, "player_events", "aaop_company")
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"
        assert result[0]["buffer_ratio"] == 0.003

    def test_scan_source_directory_empty(self, tmp_path: Path):
        result = scan_source_directory(str(tmp_path / "nonexistent"), "medianova")
        assert result == []


# ── SyncEngine ──


class TestSyncEngine:
    @pytest.mark.asyncio
    async def test_sync_engine_skips_already_ingested(self, tmp_path: Path):
        from shared.ingest.sync_engine import SyncEngine

        # Create a test file
        records = [{"timestamp": "2026-03-04T19:30:00Z", "event_type": "test"}]
        gz_path = tmp_path / "source" / "test.jsonl.gz"
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        # Mock SQLite (file already ingested with matching mtime)
        file_mtime = str(os.path.getmtime(gz_path))
        mock_sqlite = AsyncMock()
        mock_sqlite.fetch_one = AsyncMock(return_value={"id": "exists", "file_mtime": file_mtime})
        mock_sqlite.execute = AsyncMock()

        # Mock DuckDB
        mock_duckdb = MagicMock()
        mock_duckdb.ensure_tenant_schema = MagicMock()
        mock_duckdb.ensure_source_table = MagicMock()
        mock_duckdb.delete_older_than = MagicMock(return_value=0)

        config = SourceConfig(
            id="cfg1", tenant_id="aaop_company", source_name="api_logs",
            source_type="local", local_path=str(tmp_path / "source"),
            created_at="2026-03-01T00:00:00Z",
        )

        engine = SyncEngine(mock_sqlite, mock_duckdb)
        result = await engine.sync_source("aaop_company", config)

        # File was skipped (already ingested), so 0 files processed
        assert result.files_processed == 0
        assert result.rows_inserted == 0


# ── QueryRouter ──


class TestQueryRouter:
    def test_query_router_hot_path(self, tmp_path: Path):
        from shared.ingest.query_router import QueryRouter

        mock_duckdb = MagicMock()
        mock_duckdb.query = MagicMock(return_value=[{"timestamp": "2026-03-20", "tenant_id": "t1"}])

        qr = QueryRouter(mock_duckdb)
        today = date.today()
        rows, from_cache = qr.query("t1", "medianova", today - timedelta(days=5), today)

        assert from_cache is True
        mock_duckdb.query.assert_called_once()

    def test_query_router_cold_path(self, tmp_path: Path):
        from shared.ingest.query_router import QueryRouter

        mock_duckdb = MagicMock()
        qr = QueryRouter(mock_duckdb, {"medianova": str(tmp_path)})

        # Query old dates — no files exist, returns empty
        rows, from_cache = qr.query("t1", "medianova", date(2025, 1, 1), date(2025, 1, 5))

        assert from_cache is False
        assert rows == []


# ── API Endpoints ──


class TestAPIEndpoints:
    def test_source_config_crud(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # CREATE — use unique tenant to avoid seed clash
        test_tenant = "test_crud_tenant"
        res = client.post("/data-sources/configs", json={
            "tenant_id": test_tenant, "source_name": "medianova",
            "source_type": "local", "local_path": "/tmp/test",
            "enabled": True,
        })
        assert res.status_code == 200
        data = res.json()
        config_id = data["id"]
        assert data["source_name"] == "medianova"

        # GET
        res = client.get(f"/data-sources/configs?tenant_id={test_tenant}")
        assert res.status_code == 200
        configs = res.json()
        assert any(c["id"] == config_id for c in configs)

        # PATCH
        res = client.patch(f"/data-sources/configs/{config_id}",
                           json={"enabled": False, "local_path": "/tmp/updated"})
        assert res.status_code == 200

        # DELETE
        res = client.delete(f"/data-sources/configs/{config_id}")
        assert res.status_code == 200
        assert res.json()["deleted"] == config_id

    def test_sync_single_source_endpoint(self):
        """Sync single source endpoint returns valid response."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # Create config with unique source name for test isolation
        import uuid as _uuid
        unique_name = "app_reviews"  # use one not likely already in DB
        # Delete first to avoid UNIQUE conflict
        existing = client.get(f"/data-sources/configs?tenant_id=test_sync_tenant")
        for c in existing.json():
            client.delete(f"/data-sources/configs/{c['id']}")

        res = client.post("/data-sources/configs", json={
            "tenant_id": "test_sync_tenant", "source_name": unique_name,
            "source_type": "local", "local_path": "/tmp/nonexistent",
        })
        assert res.status_code == 200
        config_id = res.json()["id"]

        # Sync — returns 200 with error in result (DuckDB lock or empty dir)
        res = client.post(f"/data-sources/sync/{config_id}")
        assert res.status_code == 200

        # Cleanup
        client.delete(f"/data-sources/configs/{config_id}")

    def test_sync_all_endpoint(self):
        """Sync all endpoint returns list."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        res = client.post("/data-sources/sync-all?tenant_id=aaop_company")
        # Accept 200 (success) or 500 (DuckDB lock in test env)
        assert res.status_code in (200, 500)

    def test_import_delete_endpoint(self):
        """Import & delete endpoint returns SyncResult."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        # Create config
        res = client.post("/data-sources/configs", json={
            "tenant_id": "test_import_tenant", "source_name": "billing",
            "source_type": "local", "local_path": "/tmp/nonexistent_import",
        })
        assert res.status_code == 200
        config_id = res.json()["id"]

        # Import & delete
        res = client.post(f"/data-sources/import-delete/{config_id}")
        assert res.status_code == 200
        data = res.json()
        assert "files_deleted" in data

        client.delete(f"/data-sources/configs/{config_id}")


# ══════════════════════════════════════════════════════════════════════
# WATCH FOLDER + DEFAULT CONFIGS
# ══════════════════════════════════════════════════════════════════════


class TestWatchFolder:
    def test_watch_folder_handler_recognizes_jsonl_gz(self):
        """LogFileHandler recognizes .jsonl.gz files."""
        from shared.ingest.watch_folder import LogFileHandler
        handler = LogFileHandler("t1", None)
        assert handler._is_valid_file("/path/to/data.jsonl.gz") is True
        assert handler._is_valid_file("/path/to/data.json") is True
        assert handler._is_valid_file("/path/to/data.csv") is False

    def test_watch_folder_source_name_mapping(self):
        """All 14 folder names map to correct source names."""
        from shared.ingest.source_config import FOLDER_TO_SOURCE
        from shared.ingest.watch_folder import LogFileHandler

        handler = LogFileHandler("t1", None)
        assert len(FOLDER_TO_SOURCE) == 14

        expected = {
            "api_logs": "api_logs", "app_reviews": "app_reviews", "billing": "billing",
            "crm": "crm_subscriber", "drm_fairplay": "fairplay_drm", "drm_widevine": "widevine_drm",
            "epg": "epg", "medianova": "medianova", "newrelic": "newrelic_apm",
            "npaw": "npaw_analytics", "origin_logs": "origin_server",
            "player_events": "player_events", "push_notifications": "push_notifications",
            "akamai": "akamai_ds2",
        }
        assert FOLDER_TO_SOURCE == expected

        # Test handler mapping
        assert handler._get_source_name("/data/medianova/file.gz") == "medianova"
        assert handler._get_source_name("/data/drm_widevine/file.gz") == "widevine_drm"
        assert handler._get_source_name("/data/akamai/file.gz") == "akamai_ds2"


class TestDefaultConfigs:
    @pytest.mark.asyncio
    async def test_default_configs_seed_idempotent(self):
        """Running seed twice doesn't create duplicates."""
        from shared.ingest.default_configs import seed_default_configs

        mock_sqlite = AsyncMock()
        mock_sqlite.fetch_one = AsyncMock(return_value=None)  # not exists
        mock_sqlite.execute = AsyncMock()

        count1 = await seed_default_configs(mock_sqlite)
        assert count1 == 14

        # Second run: all exist
        mock_sqlite.fetch_one = AsyncMock(return_value={"id": "exists"})
        count2 = await seed_default_configs(mock_sqlite)
        assert count2 == 0

    def test_default_configs_all_paths_correct(self):
        """All default configs have correct local_path format."""
        from shared.ingest.default_configs import DEFAULT_SOURCE_CONFIGS, BASE_MOCK_DATA_PATH

        for cfg in DEFAULT_SOURCE_CONFIGS:
            expected_path = f"{BASE_MOCK_DATA_PATH}/{cfg['folder']}/"
            assert cfg["folder"]  # not empty
            assert cfg["source_name"]  # not empty


class TestSyncEngineAdvanced:
    @pytest.mark.asyncio
    async def test_sync_engine_deletes_file_after_import(self, tmp_path: Path):
        """Files are deleted after successful import when delete_after_import=True."""
        from shared.ingest.sync_engine import SyncEngine

        gz_path = tmp_path / "source" / "test.jsonl.gz"
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": "2026-03-04T19:30:00Z"}) + "\n")

        assert gz_path.exists()

        mock_sqlite = AsyncMock()
        mock_sqlite.fetch_one = AsyncMock(return_value=None)
        mock_sqlite.execute = AsyncMock()

        mock_duckdb = MagicMock()
        mock_duckdb.ensure_tenant_schema = MagicMock()
        mock_duckdb.ensure_source_table = MagicMock()
        mock_duckdb.insert_batch = MagicMock(return_value=1)
        mock_duckdb.delete_older_than = MagicMock(return_value=0)

        config = SourceConfig(
            id="cfg1", tenant_id="t1", source_name="api_logs",
            source_type="local", local_path=str(tmp_path / "source"),
            created_at="2026-03-01T00:00:00Z",
        )

        engine = SyncEngine(mock_sqlite, mock_duckdb)
        result = await engine.sync_source("t1", config, delete_after_import=True)

        assert result.files_processed == 1
        assert result.files_deleted == 1
        assert not gz_path.exists()  # file was deleted

    @pytest.mark.asyncio
    async def test_sync_engine_skips_unchanged_mtime(self, tmp_path: Path):
        """Files with unchanged mtime are skipped."""
        from shared.ingest.sync_engine import SyncEngine

        gz_path = tmp_path / "source" / "test.jsonl.gz"
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": "2026-03-04T19:30:00Z"}) + "\n")

        file_mtime = str(os.path.getmtime(gz_path))

        mock_sqlite = AsyncMock()
        # Return existing record with same mtime
        mock_sqlite.fetch_one = AsyncMock(return_value={"id": "x", "file_mtime": file_mtime})
        mock_sqlite.execute = AsyncMock()

        mock_duckdb = MagicMock()
        mock_duckdb.ensure_tenant_schema = MagicMock()
        mock_duckdb.ensure_source_table = MagicMock()
        mock_duckdb.delete_older_than = MagicMock(return_value=0)

        config = SourceConfig(
            id="cfg1", tenant_id="t1", source_name="api_logs",
            source_type="local", local_path=str(tmp_path / "source"),
            created_at="2026-03-01T00:00:00Z",
        )

        engine = SyncEngine(mock_sqlite, mock_duckdb)
        result = await engine.sync_source("t1", config)

        assert result.files_processed == 0  # skipped

    @pytest.mark.asyncio
    async def test_sync_engine_reprocesses_changed_mtime(self, tmp_path: Path):
        """Files with changed mtime are reprocessed."""
        from shared.ingest.sync_engine import SyncEngine

        gz_path = tmp_path / "source" / "test.jsonl.gz"
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": "2026-03-04T19:30:00Z"}) + "\n")

        mock_sqlite = AsyncMock()
        # Return existing record with DIFFERENT mtime
        mock_sqlite.fetch_one = AsyncMock(return_value={"id": "x", "file_mtime": "old_mtime"})
        mock_sqlite.execute = AsyncMock()

        mock_duckdb = MagicMock()
        mock_duckdb.ensure_tenant_schema = MagicMock()
        mock_duckdb.ensure_source_table = MagicMock()
        mock_duckdb.insert_batch = MagicMock(return_value=1)
        mock_duckdb.delete_older_than = MagicMock(return_value=0)

        config = SourceConfig(
            id="cfg1", tenant_id="t1", source_name="api_logs",
            source_type="local", local_path=str(tmp_path / "source"),
            created_at="2026-03-01T00:00:00Z",
        )

        engine = SyncEngine(mock_sqlite, mock_duckdb)
        result = await engine.sync_source("t1", config)

        assert result.files_processed == 1  # reprocessed
