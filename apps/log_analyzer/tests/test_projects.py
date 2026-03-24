"""Tests for projects: CRUD with new fields, summary endpoint."""

from __future__ import annotations

import aiosqlite
import pytest


@pytest.fixture
async def project_db():
    """In-memory SQLite with log_projects + scheduled_tasks tables."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("""
            CREATE TABLE log_projects (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                sub_module TEXT NOT NULL,
                config_json TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                description TEXT DEFAULT '',
                source_type TEXT DEFAULT 'akamai_ds2',
                cp_code TEXT DEFAULT '',
                fetch_mode TEXT DEFAULT 'sampled',
                default_date_range TEXT DEFAULT 'last_1_day'
            )
        """)
        await conn.execute("""
            CREATE TABLE scheduled_tasks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                project_id TEXT,
                name TEXT NOT NULL,
                schedule_cron TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await conn.commit()
        yield conn


@pytest.mark.asyncio
async def test_create_project_with_fields(project_db: aiosqlite.Connection):
    """Create project with name + cp_code + fetch_mode → persists."""
    await project_db.execute(
        """INSERT INTO log_projects (id, tenant_id, name, sub_module, description, source_type, cp_code, fetch_mode, default_date_range)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("proj1", "s_sport_plus", "CDN Live", "akamai", "Live stream analysis",
         "akamai_ds2", "60890", "full", "last_1_week"),
    )
    await project_db.commit()

    cursor = await project_db.execute("SELECT * FROM log_projects WHERE id = ?", ("proj1",))
    row = await cursor.fetchone()
    assert row is not None
    assert row["name"] == "CDN Live"
    assert row["cp_code"] == "60890"
    assert row["fetch_mode"] == "full"
    assert row["default_date_range"] == "last_1_week"
    assert row["description"] == "Live stream analysis"
    assert row["source_type"] == "akamai_ds2"


@pytest.mark.asyncio
async def test_project_summary_no_jobs(project_db: aiosqlite.Connection):
    """New project → scheduled_tasks_count is 0."""
    await project_db.execute(
        "INSERT INTO log_projects (id, tenant_id, name, sub_module) VALUES (?, ?, ?, ?)",
        ("proj2", "s_sport_plus", "Empty Project", "akamai"),
    )
    await project_db.commit()

    # No scheduled tasks
    cursor = await project_db.execute(
        "SELECT COUNT(*) as cnt FROM scheduled_tasks WHERE project_id = ? AND is_active = 1",
        ("proj2",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 0


@pytest.mark.asyncio
async def test_project_summary_with_tasks(project_db: aiosqlite.Connection):
    """Project with scheduled tasks → count reflects active tasks."""
    await project_db.execute(
        "INSERT INTO log_projects (id, tenant_id, name, sub_module) VALUES (?, ?, ?, ?)",
        ("proj3", "s_sport_plus", "With Tasks", "akamai"),
    )
    await project_db.execute(
        "INSERT INTO scheduled_tasks (id, tenant_id, project_id, name, schedule_cron, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        ("task1", "s_sport_plus", "proj3", "Daily", "0 3 * * *", 1),
    )
    await project_db.execute(
        "INSERT INTO scheduled_tasks (id, tenant_id, project_id, name, schedule_cron, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        ("task2", "s_sport_plus", "proj3", "Weekly", "0 0 * * 1", 1),
    )
    await project_db.execute(
        "INSERT INTO scheduled_tasks (id, tenant_id, project_id, name, schedule_cron, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        ("task3", "s_sport_plus", "proj3", "Disabled", "0 0 * * *", 0),
    )
    await project_db.commit()

    cursor = await project_db.execute(
        "SELECT COUNT(*) as cnt FROM scheduled_tasks WHERE project_id = ? AND is_active = 1",
        ("proj3",),
    )
    row = await cursor.fetchone()
    assert row["cnt"] == 2  # Only active tasks
