"""Seed mock data for Capacity & Cost."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient

logger = structlog.get_logger(__name__)

_SERVICES = ["cdn_bandwidth", "origin_cpu", "origin_memory", "encoder_queue", "api_gateway", "cache_hit_rate", "concurrent_streams"]
_REGIONS = ["eu-west", "eu-central", "me-south"]
_PEAK_HOURS = {19, 20, 21, 22}
_SPIKE_HOURS = {20, 21}

_JOBS = [
    ("CDN Cache Purge", "cache_purge", "active", "0 */4 * * *"),
    ("Origin Health Check", "health_check", "active", "*/5 * * * *"),
    ("Scale Up Encoder", "scale_up", "active", "0 18 * * *"),
    ("Bandwidth Report", "report", "active", "0 6 * * 1"),
    ("Anomaly Threshold Tune", "tune", "paused", "0 3 * * 0"),
    ("Log Cleanup", "cleanup", "active", "0 2 * * *"),
    ("DRM Key Rotation", "security", "active", "0 0 1 * *"),
    ("Cost Optimizer", "optimization", "completed", "0 1 * * 1"),
    ("SSL Cert Check", "security", "active", "0 8 * * *"),
    ("Backup Verify", "backup", "paused", "0 4 * * *"),
]


async def seed_capacity_cost_mock_data(
    duck: DuckDBClient,
    sqlite: SQLiteClient,
    tenant_id: str = "s_sport_plus",
) -> None:
    """Seed capacity metrics + automation jobs. Idempotent."""
    duck.execute("""CREATE TABLE IF NOT EXISTS shared_analytics.capacity_metrics (
        id VARCHAR, tenant_id VARCHAR, service VARCHAR, metric_name VARCHAR,
        current_value DOUBLE, capacity_limit DOUBLE, utilization_pct DOUBLE,
        timestamp VARCHAR, region VARCHAR
    )""")

    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.capacity_metrics WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 20:
            logger.info("capacity_seed_skipped", existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # 150 capacity metrics (7 services × ~21 hours + extras)
    for svc in _SERVICES:
        limit_val = {"cdn_bandwidth": 10000, "origin_cpu": 100, "origin_memory": 100,
                     "encoder_queue": 500, "api_gateway": 5000, "cache_hit_rate": 100,
                     "concurrent_streams": 100000}.get(svc, 100)

        for h in range(24):
            ts = (now - timedelta(hours=24 - h)).replace(minute=0, second=0)
            if h in _SPIKE_HOURS:
                pct = round(random.uniform(85, 98), 1)
            elif h in _PEAK_HOURS:
                pct = round(random.uniform(70, 90), 1)
            else:
                pct = round(random.uniform(35, 70), 1)

            current = round(limit_val * pct / 100, 1)
            try:
                duck.execute(
                    """INSERT INTO shared_analytics.capacity_metrics
                       (id, tenant_id, service, metric_name, current_value, capacity_limit,
                        utilization_pct, timestamp, region)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [f"CAP-{uuid4().hex[:8]}", tenant_id, svc, f"{svc}_utilization",
                     current, limit_val, pct, ts.isoformat(), random.choice(_REGIONS)],
                )
            except Exception:
                pass

    # SQLite automation jobs
    await sqlite.execute("""CREATE TABLE IF NOT EXISTS automation_jobs (
        id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT, job_type TEXT,
        status TEXT, schedule TEXT, last_run TEXT, next_run TEXT,
        config_json TEXT, created_at TEXT DEFAULT (datetime('now'))
    )""")

    existing = await sqlite.fetch_one("SELECT COUNT(*) as cnt FROM automation_jobs WHERE tenant_id = ?", (tenant_id,))
    if not existing or existing.get("cnt", 0) < 5:
        for name, jtype, status, sched in _JOBS:
            await sqlite.execute(
                "INSERT OR IGNORE INTO automation_jobs (id, tenant_id, name, job_type, status, schedule, last_run, config_json) VALUES (?,?,?,?,?,?,?,?)",
                (f"JOB-{uuid4().hex[:8]}", tenant_id, name, jtype, status, sched,
                 (now - timedelta(hours=random.randint(1, 48))).isoformat(), "{}"),
            )

    logger.info("capacity_seed_complete", tenant_id=tenant_id)
