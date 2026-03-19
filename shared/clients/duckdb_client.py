"""DuckDB wrapper for shared analytics. GCP migration: swap to BigQuery adaptor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import structlog

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)

INIT_SQL = """
CREATE SCHEMA IF NOT EXISTS shared_analytics;

CREATE TABLE IF NOT EXISTS shared_analytics.cdn_analysis (
    analysis_id     VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    project_id      VARCHAR,
    sub_module      VARCHAR NOT NULL,
    analysis_time   TIMESTAMPTZ NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    total_requests  BIGINT,
    error_rate      DOUBLE,
    cache_hit_rate  DOUBLE,
    avg_ttfb_ms     DOUBLE,
    p99_ttfb_ms     DOUBLE,
    top_errors      JSON,
    edge_breakdown  JSON,
    anomalies       JSON,
    agent_summary   TEXT,
    report_path     VARCHAR,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_analytics.incidents (
    incident_id     VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    severity        VARCHAR NOT NULL,
    title           VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,
    source_app      VARCHAR,
    correlation_ids JSON,
    affected_svcs   JSON,
    metrics_at_time JSON,
    rca_id          VARCHAR,
    mttr_seconds    INTEGER,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_analytics.qoe_metrics (
    metric_id       VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    session_id      VARCHAR NOT NULL,
    user_id_hash    VARCHAR,
    content_id      VARCHAR,
    device_type     VARCHAR,
    region          VARCHAR,
    buffering_ratio DOUBLE,
    startup_time_ms INTEGER,
    bitrate_avg     INTEGER,
    quality_score   DOUBLE,
    errors          JSON,
    event_ts        TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_analytics.live_events (
    event_id        VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    event_name      VARCHAR NOT NULL,
    sport           VARCHAR,
    competition     VARCHAR,
    kickoff_time    TIMESTAMPTZ,
    status          VARCHAR,
    expected_viewers INTEGER,
    peak_viewers    INTEGER,
    pre_scale_done  BOOLEAN DEFAULT FALSE,
    sportradar_id   VARCHAR,
    epg_id          VARCHAR,
    metrics         JSON,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_analytics.agent_decisions (
    decision_id         VARCHAR PRIMARY KEY,
    tenant_id           VARCHAR NOT NULL,
    app                 VARCHAR NOT NULL,
    action              VARCHAR NOT NULL,
    risk_level          VARCHAR NOT NULL,
    approval_required   BOOLEAN DEFAULT FALSE,
    llm_model_used      VARCHAR NOT NULL,
    reasoning_summary   TEXT,
    tools_executed      JSON,
    confidence_score    DOUBLE,
    duration_ms         INTEGER,
    input_event_id      VARCHAR,
    output_event_type   VARCHAR,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_analytics.alerts_sent (
    alert_id        VARCHAR PRIMARY KEY,
    tenant_id       VARCHAR NOT NULL,
    source_app      VARCHAR NOT NULL,
    severity        VARCHAR NOT NULL,
    channel         VARCHAR NOT NULL,
    title           VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,
    decision_id     VARCHAR,
    sent_at         TIMESTAMPTZ NOT NULL,
    acked_at        TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
"""


class DuckDBClient:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or get_settings().duckdb_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self._db_path)
        logger.info("duckdb_connected", path=self._db_path)

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("duckdb_disconnected")

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            msg = "DuckDBClient not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._conn

    def execute(self, sql: str, params: list[Any] | None = None) -> duckdb.DuckDBPyConnection:
        if params:
            return self.conn.execute(sql, params)
        return self.conn.execute(sql)

    def fetch_all(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        rel = self.execute(sql, params)
        columns = [desc[0] for desc in rel.description]
        rows = rel.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def fetch_one(self, sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
        rel = self.execute(sql, params)
        columns = [desc[0] for desc in rel.description]
        row = rel.fetchone()
        return dict(zip(columns, row, strict=False)) if row else None

    def init_tables(self) -> None:
        """Create shared_analytics schema and all tables."""
        self.conn.execute(INIT_SQL)
        logger.info("duckdb_tables_initialized")
