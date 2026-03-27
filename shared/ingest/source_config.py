"""Source configuration models + SQLite persistence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceType = Literal["local", "s3"]

VALID_SOURCE_NAMES = [
    "medianova", "origin_server", "widevine_drm", "fairplay_drm",
    "player_events", "npaw_analytics", "api_logs", "newrelic_apm",
    "crm_subscriber", "epg", "billing", "push_notifications", "app_reviews",
]

SOURCE_CONFIG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_source_configs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    local_path TEXT,
    s3_bucket TEXT,
    s3_prefix TEXT,
    enabled INTEGER DEFAULT 1,
    sync_interval_minutes INTEGER,
    last_sync_at TEXT,
    last_sync_rows INTEGER,
    last_sync_error TEXT,
    created_at TEXT,
    UNIQUE(tenant_id, source_name)
)
"""

INGESTION_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    source_name TEXT,
    file_path TEXT,
    rows_ingested INTEGER,
    ingested_at TEXT,
    UNIQUE(tenant_id, file_path)
)
"""


class SourceConfig(BaseModel):
    id: str
    tenant_id: str
    source_name: str
    source_type: SourceType
    local_path: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    enabled: bool = True
    sync_interval_minutes: int | None = None
    last_sync_at: str | None = None
    last_sync_rows: int | None = None
    last_sync_error: str | None = None
    created_at: str


class SourceConfigCreate(BaseModel):
    tenant_id: str
    source_name: str
    source_type: SourceType
    local_path: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    enabled: bool = True
    sync_interval_minutes: int | None = None


class SyncResult(BaseModel):
    source_name: str
    files_processed: int
    rows_inserted: int
    rows_deleted_from_cache: int
    errors: list[str]
    duration_ms: int
