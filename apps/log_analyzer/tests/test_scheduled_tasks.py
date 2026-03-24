"""Tests for scheduled tasks: CRUD, emails, run now."""

from __future__ import annotations

import json

import aiosqlite
import pytest


@pytest.fixture
async def task_db():
    """In-memory SQLite with scheduled_tasks table."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("""
            CREATE TABLE scheduled_tasks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                project_id TEXT,
                name TEXT NOT NULL,
                cp_code TEXT,
                s3_bucket TEXT,
                s3_prefix TEXT,
                schedule_cron TEXT NOT NULL,
                fetch_mode TEXT DEFAULT 'sampled',
                is_active INTEGER DEFAULT 1,
                notify_emails TEXT DEFAULT '[]',
                last_run TEXT,
                last_status TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                bq_export_enabled TEXT DEFAULT '0',
                bq_export_categories TEXT DEFAULT '[]'
            )
        """)
        await conn.commit()
        yield conn


@pytest.mark.asyncio
async def test_create_task(task_db: aiosqlite.Connection):
    """Create task → persists in SQLite."""
    await task_db.execute(
        """INSERT INTO scheduled_tasks (id, tenant_id, name, schedule_cron, cp_code, s3_bucket, fetch_mode)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("task1", "s_sport_plus", "Daily Fetch", "0 3 * * *", "60890", "ssport-datastream", "sampled"),
    )
    await task_db.commit()

    cursor = await task_db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", ("task1",))
    row = await cursor.fetchone()
    assert row is not None
    assert row["name"] == "Daily Fetch"
    assert row["schedule_cron"] == "0 3 * * *"
    assert row["fetch_mode"] == "sampled"
    assert row["is_active"] == 1


@pytest.mark.asyncio
async def test_task_emails(task_db: aiosqlite.Connection):
    """Add emails to notify_emails JSON array."""
    emails = ["admin@ssportplus.com", "ops@ssportplus.com"]
    await task_db.execute(
        """INSERT INTO scheduled_tasks (id, tenant_id, name, schedule_cron, notify_emails)
           VALUES (?, ?, ?, ?, ?)""",
        ("task2", "s_sport_plus", "Email Task", "0 */6 * * *", json.dumps(emails)),
    )
    await task_db.commit()

    cursor = await task_db.execute("SELECT notify_emails FROM scheduled_tasks WHERE id = ?", ("task2",))
    row = await cursor.fetchone()
    loaded = json.loads(row["notify_emails"])
    assert len(loaded) == 2
    assert "admin@ssportplus.com" in loaded
    assert "ops@ssportplus.com" in loaded

    # Add another email
    loaded.append("devops@ssportplus.com")
    await task_db.execute(
        "UPDATE scheduled_tasks SET notify_emails = ? WHERE id = ?",
        (json.dumps(loaded), "task2"),
    )
    await task_db.commit()

    cursor = await task_db.execute("SELECT notify_emails FROM scheduled_tasks WHERE id = ?", ("task2",))
    row = await cursor.fetchone()
    updated = json.loads(row["notify_emails"])
    assert len(updated) == 3


@pytest.mark.asyncio
async def test_run_now(task_db: aiosqlite.Connection):
    """Run now updates last_run and last_status."""
    await task_db.execute(
        """INSERT INTO scheduled_tasks (id, tenant_id, name, schedule_cron)
           VALUES (?, ?, ?, ?)""",
        ("task3", "s_sport_plus", "Run Now Task", "0 3 * * *"),
    )
    await task_db.commit()

    # Simulate "run now" by updating last_run + last_status
    await task_db.execute(
        "UPDATE scheduled_tasks SET last_run = datetime('now'), last_status = 'running' WHERE id = ?",
        ("task3",),
    )
    await task_db.commit()

    cursor = await task_db.execute("SELECT last_run, last_status FROM scheduled_tasks WHERE id = ?", ("task3",))
    row = await cursor.fetchone()
    assert row["last_status"] == "running"
    assert row["last_run"] is not None


@pytest.mark.asyncio
async def test_delete_task(task_db: aiosqlite.Connection):
    """Delete task removes from SQLite."""
    await task_db.execute(
        "INSERT INTO scheduled_tasks (id, tenant_id, name, schedule_cron) VALUES (?, ?, ?, ?)",
        ("task4", "s_sport_plus", "Delete Me", "0 3 * * *"),
    )
    await task_db.commit()

    await task_db.execute("DELETE FROM scheduled_tasks WHERE id = ?", ("task4",))
    await task_db.commit()

    cursor = await task_db.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE id = ?", ("task4",))
    count = await cursor.fetchone()
    assert count[0] == 0


@pytest.mark.asyncio
async def test_bq_export_fields(task_db: aiosqlite.Connection):
    """Task with bq_export_enabled=1 + categories → persists."""
    categories = json.dumps(["meta", "timing", "traffic", "cache"])
    await task_db.execute(
        """INSERT INTO scheduled_tasks (id, tenant_id, name, schedule_cron, bq_export_enabled, bq_export_categories)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("task5", "s_sport_plus", "BQ Export Task", "0 3 * * *", "1", categories),
    )
    await task_db.commit()

    cursor = await task_db.execute("SELECT bq_export_enabled, bq_export_categories FROM scheduled_tasks WHERE id = ?", ("task5",))
    row = await cursor.fetchone()
    assert row["bq_export_enabled"] == "1"
    loaded = json.loads(row["bq_export_categories"])
    assert len(loaded) == 4
    assert "meta" in loaded
    assert "cache" in loaded
