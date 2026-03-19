"""Tests for shared/clients/sqlite_client.py."""

from __future__ import annotations

import pytest

from shared.clients.sqlite_client import SQLiteClient


@pytest.mark.asyncio
async def test_connect_and_init(sqlite_client: SQLiteClient):
    # Tables should exist after init
    rows = await sqlite_client.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [r["name"] for r in rows]
    assert "tenants" in table_names
    assert "users" in table_names
    assert "module_configs" in table_names
    assert "audit_log" in table_names


@pytest.mark.asyncio
async def test_insert_and_fetch(sqlite_client: SQLiteClient):
    await sqlite_client.execute(
        "INSERT INTO tenants (id, name, plan) VALUES (?, ?, ?)",
        ("bein_sports", "beIN Sports", "enterprise"),
    )
    row = await sqlite_client.fetch_one("SELECT * FROM tenants WHERE id = ?", ("bein_sports",))
    assert row is not None
    assert row["name"] == "beIN Sports"
    assert row["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_fetch_all(sqlite_client: SQLiteClient):
    await sqlite_client.execute("INSERT INTO tenants (id, name, plan) VALUES (?, ?, ?)", ("t1", "T1", "starter"))
    await sqlite_client.execute("INSERT INTO tenants (id, name, plan) VALUES (?, ?, ?)", ("t2", "T2", "growth"))
    rows = await sqlite_client.fetch_all("SELECT * FROM tenants ORDER BY id")
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fetch_one_not_found(sqlite_client: SQLiteClient):
    row = await sqlite_client.fetch_one("SELECT * FROM tenants WHERE id = ?", ("nonexistent",))
    assert row is None


@pytest.mark.asyncio
async def test_not_connected_raises():
    client = SQLiteClient(db_path="/tmp/nonexistent.db")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = client.conn
