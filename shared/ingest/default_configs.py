"""Auto-seed default source configs for aaop_company tenant."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

BASE_MOCK_DATA_PATH = os.environ.get(
    "MOCK_DATA_BASE_PATH",
    "/Users/fatihayaz/Documents/Projects/AAOP/aaop-mock-data",
)
DEFAULT_TENANT = "aaop_company"

DEFAULT_SOURCE_CONFIGS = [
    {"source_name": "medianova", "folder": "medianova"},
    {"source_name": "origin_server", "folder": "origin_logs"},
    {"source_name": "widevine_drm", "folder": "drm_widevine"},
    {"source_name": "fairplay_drm", "folder": "drm_fairplay"},
    {"source_name": "player_events", "folder": "player_events"},
    {"source_name": "npaw_analytics", "folder": "npaw"},
    {"source_name": "api_logs", "folder": "api_logs"},
    {"source_name": "newrelic_apm", "folder": "newrelic"},
    {"source_name": "crm_subscriber", "folder": "crm"},
    {"source_name": "epg", "folder": "epg"},
    {"source_name": "billing", "folder": "billing"},
    {"source_name": "push_notifications", "folder": "push_notifications"},
    {"source_name": "app_reviews", "folder": "app_reviews"},
    {"source_name": "akamai_ds2", "folder": "akamai"},
]


async def seed_default_configs(sqlite_client) -> int:
    """Seed default source configs if they don't already exist. Returns count of new configs."""
    seeded = 0
    now = datetime.now(timezone.utc).isoformat()

    for cfg in DEFAULT_SOURCE_CONFIGS:
        source_name = cfg["source_name"]
        folder = cfg["folder"]
        local_path = f"{BASE_MOCK_DATA_PATH}/{folder}/"

        # Check if exists
        existing = await sqlite_client.fetch_one(
            "SELECT id FROM data_source_configs WHERE tenant_id = ? AND source_name = ?",
            (DEFAULT_TENANT, source_name),
        )
        if existing:
            continue

        config_id = str(uuid.uuid4())[:12]
        await sqlite_client.execute(
            """INSERT INTO data_source_configs
               (id, tenant_id, source_name, source_type, local_path, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (config_id, DEFAULT_TENANT, source_name, "local", local_path, now),
        )
        seeded += 1

    logger.info("default_configs_seeded", tenant=DEFAULT_TENANT, new_configs=seeded,
                total=len(DEFAULT_SOURCE_CONFIGS))
    return seeded
