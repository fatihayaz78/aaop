"""Seed mock data for Growth & Retention."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient

logger = structlog.get_logger(__name__)

_SEGMENTS = ["power_user"] * 20 + ["regular"] * 50 + ["at_risk"] * 20 + ["churned"] * 10


def seed_growth_retention_mock_data(duck: DuckDBClient, tenant_id: str = "s_sport_plus") -> None:
    """Seed 100 retention scores. Idempotent."""
    duck.execute("""CREATE TABLE IF NOT EXISTS shared_analytics.retention_scores (
        id VARCHAR, tenant_id VARCHAR, user_id_hash VARCHAR, churn_risk DOUBLE,
        qoe_score DOUBLE, cdn_score DOUBLE, retention_trend DOUBLE,
        segment VARCHAR, last_active VARCHAR, created_at VARCHAR
    )""")

    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.retention_scores WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 20:
            logger.info("growth_seed_skipped", existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    segments = list(_SEGMENTS)
    random.shuffle(segments)

    for i in range(100):
        seg = segments[i % len(segments)]
        if seg == "churned":
            churn = round(random.uniform(0.8, 0.99), 3)
        elif seg == "at_risk":
            churn = round(random.uniform(0.5, 0.85), 3)
        elif seg == "regular":
            churn = round(random.uniform(0.2, 0.5), 3)
        else:
            churn = round(random.uniform(0.01, 0.2), 3)

        qoe = round(max(0.5, 5.0 - churn * 4 + random.uniform(-0.5, 0.5)), 2)
        uid = hashlib.sha256(f"user-{i}-{uuid4().hex[:4]}".encode()).hexdigest()[:16]

        try:
            duck.execute(
                """INSERT INTO shared_analytics.retention_scores
                   (id, tenant_id, user_id_hash, churn_risk, qoe_score, cdn_score,
                    retention_trend, segment, last_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [f"RS-{uuid4().hex[:10]}", tenant_id, uid, churn, qoe,
                 round(random.uniform(0.5, 1.0), 2), round(random.uniform(-0.1, 0.1), 3),
                 seg, (now - timedelta(days=random.randint(0, 30))).isoformat(),
                 now.isoformat()],
            )
        except Exception:
            pass

    logger.info("growth_seed_complete", tenant_id=tenant_id, rows=100)
