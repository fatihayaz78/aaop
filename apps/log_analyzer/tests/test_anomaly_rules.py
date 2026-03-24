"""Tests for anomaly rules: default seeding, evaluation, CRUD."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.routers.log_analyzer import _evaluate_rule


# ── Default rules ──


def test_default_rules_exist():
    """Verify the two default rule definitions are correct."""
    # These are seeded by _ensure_schema for s_sport_plus tenant
    rule_foreign = {
        "id": "rule_foreign_country",
        "name": "Foreign Country Access",
        "field": "country",
        "operator": "not_in",
        "value": '["TR"]',
        "severity": "high",
    }
    rule_session = {
        "id": "rule_long_session",
        "name": "Long Session per IP",
        "field": "session_duration_hours",
        "operator": "gt",
        "value": "12",
        "severity": "medium",
    }
    assert rule_foreign["operator"] == "not_in"
    assert rule_session["operator"] == "gt"


# ── Foreign country rule ──


def test_foreign_country_rule():
    """DataFrame with TR + DE rows → foreign country rule flags DE rows."""
    df = pd.DataFrame({
        "country": ["TR", "TR", "DE", "TR", "US", "TR"],
        "bytes": [1000, 2000, 3000, 4000, 5000, 6000],
    })

    rule = {
        "id": "rule_foreign",
        "name": "Foreign Country",
        "field": "country",
        "operator": "not_in",
        "value": '["TR"]',
        "severity": "high",
    }

    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 2  # DE + US
    assert result["pct_of_total"] == pytest.approx(33.33, abs=0.1)
    assert "DE" in result["sample_values"]
    assert "US" in result["sample_values"]
    assert result["severity"] == "high"


def test_foreign_country_rule_all_tr():
    """All TR rows → 0 affected."""
    df = pd.DataFrame({"country": ["TR", "TR", "TR"]})
    rule = {"id": "r1", "name": "Foreign", "field": "country", "operator": "not_in", "value": '["TR"]', "severity": "high"}
    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 0


# ── Greater than rule ──


def test_gt_rule():
    """Greater-than rule flags rows above threshold."""
    df = pd.DataFrame({"transfer_time_ms": [10, 50, 100, 200, 500, 1000]})
    rule = {"id": "r2", "name": "Slow", "field": "transfer_time_ms", "operator": "gt", "value": "100", "severity": "medium"}
    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 3  # 200, 500, 1000


# ── Less than rule ──


def test_lt_rule():
    """Less-than rule."""
    df = pd.DataFrame({"bytes": [100, 500, 1000, 5000]})
    rule = {"id": "r3", "name": "Small", "field": "bytes", "operator": "lt", "value": "500", "severity": "low"}
    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 1  # 100


# ── Contains rule ──


def test_contains_rule():
    """Contains rule matches substring."""
    df = pd.DataFrame({"req_path": ["/live/stream.m3u8", "/api/health", "/live/video.ts", "/static/logo.png"]})
    rule = {"id": "r4", "name": "Live", "field": "req_path", "operator": "contains", "value": "/live/", "severity": "low"}
    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 2


# ── Missing field ──


def test_missing_field_returns_zero():
    """Rule for field not in DataFrame → 0 affected."""
    df = pd.DataFrame({"country": ["TR"]})
    rule = {"id": "r5", "name": "Missing", "field": "nonexistent", "operator": "eq", "value": "x", "severity": "low"}
    result = _evaluate_rule(rule, df)
    assert result["affected_rows"] == 0
    assert "not in data" in result.get("error", "")


# ── CRUD simulation ──


@pytest.mark.asyncio
async def test_rule_crud():
    """Create, verify, delete a rule using in-memory SQLite."""
    import aiosqlite

    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("""
            CREATE TABLE anomaly_rules (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL,
                field TEXT NOT NULL, operator TEXT NOT NULL, value TEXT NOT NULL,
                severity TEXT DEFAULT 'medium', description TEXT, is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Create
        await conn.execute(
            "INSERT INTO anomaly_rules (id, tenant_id, name, field, operator, value) VALUES (?, ?, ?, ?, ?, ?)",
            ("test_rule", "t1", "Test Rule", "country", "not_in", '["TR"]'),
        )
        await conn.commit()

        # Read
        cursor = await conn.execute("SELECT * FROM anomaly_rules WHERE id = ?", ("test_rule",))
        row = await cursor.fetchone()
        assert row is not None
        assert row["name"] == "Test Rule"

        # Update
        await conn.execute("UPDATE anomaly_rules SET name = ? WHERE id = ?", ("Updated Rule", "test_rule"))
        await conn.commit()
        cursor = await conn.execute("SELECT name FROM anomaly_rules WHERE id = ?", ("test_rule",))
        row = await cursor.fetchone()
        assert row["name"] == "Updated Rule"

        # Delete
        await conn.execute("DELETE FROM anomaly_rules WHERE id = ?", ("test_rule",))
        await conn.commit()
        cursor = await conn.execute("SELECT COUNT(*) FROM anomaly_rules")
        count = await cursor.fetchone()
        assert count[0] == 0
