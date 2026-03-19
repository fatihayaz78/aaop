"""Tests for shared/clients/duckdb_client.py."""

from __future__ import annotations

import pytest

from shared.clients.duckdb_client import DuckDBClient


def test_connect_and_init(duckdb_client: DuckDBClient):
    # Verify tables exist
    rows = duckdb_client.fetch_all(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'shared_analytics' ORDER BY table_name"
    )
    table_names = [r["table_name"] for r in rows]
    assert "agent_decisions" in table_names
    assert "cdn_analysis" in table_names
    assert "incidents" in table_names
    assert "qoe_metrics" in table_names
    assert "live_events" in table_names
    assert "alerts_sent" in table_names


def test_insert_and_fetch(duckdb_client: DuckDBClient):
    duckdb_client.execute(
        """
        INSERT INTO shared_analytics.agent_decisions
        (decision_id, tenant_id, app, action, risk_level, llm_model_used)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ["d1", "t1", "ops_center", "create_incident", "MEDIUM", "claude-sonnet-4-20250514"],
    )
    row = duckdb_client.fetch_one("SELECT * FROM shared_analytics.agent_decisions WHERE decision_id = ?", ["d1"])
    assert row is not None
    assert row["app"] == "ops_center"


def test_fetch_all_empty(duckdb_client: DuckDBClient):
    rows = duckdb_client.fetch_all("SELECT * FROM shared_analytics.incidents")
    assert rows == []


def test_not_connected_raises():
    client = DuckDBClient(db_path="/tmp/test_not_connected.duckdb")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = client.conn
