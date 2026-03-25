"""Seed mock data for Live Intelligence — live events."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient

logger = structlog.get_logger(__name__)


def seed_live_intelligence_mock_data(duck: DuckDBClient, tenant_id: str = "s_sport_plus") -> None:
    """Seed 15 live events. Idempotent."""
    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.live_events WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 5:
            logger.info("live_seed_skipped", tenant_id=tenant_id, existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # Upcoming (5)
    upcoming = [
        ("Galatasaray vs Fenerbahce", "football", "Super Lig", now + timedelta(days=11, hours=17), 850000),
        ("Champions League QF - Real Madrid vs Man City", "football", "Champions League", now + timedelta(days=14, hours=18), 1200000),
        ("Besiktas vs Trabzonspor", "football", "Super Lig", now + timedelta(days=18, hours=16), 620000),
        ("Europa League SF", "football", "Europa League", now + timedelta(days=16, hours=18), 450000),
        ("Super Lig Week 28", "football", "Super Lig", now + timedelta(days=21, hours=16), 380000),
    ]

    # Live (2)
    live = [
        ("NBA Playoffs Game 3 - Lakers vs Celtics", "basketball", "NBA", now - timedelta(minutes=30), 420000),
        ("Formula 1 Qualifying - Bahrain GP", "motorsport", "Formula 1", now - timedelta(minutes=45), 310000),
    ]

    # Completed (8)
    completed = [
        ("Fenerbahce vs Galatasaray", "football", "Super Lig", now - timedelta(days=2, hours=3), 920000),
        ("Champions League GS - Liverpool vs Barcelona", "football", "Champions League", now - timedelta(days=3, hours=5), 1100000),
        ("Besiktas vs Antalyaspor", "football", "Super Lig", now - timedelta(days=1, hours=2), 380000),
        ("NBA Regular Season - Warriors vs Bucks", "basketball", "NBA", now - timedelta(days=4, hours=8), 250000),
        ("Formula 1 Race - Saudi Arabia", "motorsport", "Formula 1", now - timedelta(days=5, hours=6), 480000),
        ("Super Lig Week 27 Highlights", "football", "Super Lig", now - timedelta(days=6, hours=4), 150000),
        ("EuroLeague - Anadolu Efes vs Real Madrid", "basketball", "EuroLeague", now - timedelta(days=2, hours=7), 180000),
        ("WTA Final - Istanbul Open", "tennis", "WTA", now - timedelta(days=3, hours=4), 95000),
    ]

    for title, sport, comp, kickoff, viewers in upcoming:
        _insert_event(duck, tenant_id, title, sport, comp, kickoff, "scheduled", viewers, None, now)

    for title, sport, comp, kickoff, viewers in live:
        _insert_event(duck, tenant_id, title, sport, comp, kickoff, "live", viewers,
                      random.randint(int(viewers * 0.7), viewers), now)

    for title, sport, comp, kickoff, viewers in completed:
        _insert_event(duck, tenant_id, title, sport, comp, kickoff, "completed", viewers,
                      random.randint(int(viewers * 0.8), int(viewers * 1.1)), now)

    logger.info("live_seed_complete", tenant_id=tenant_id, events=15)


def _insert_event(duck, tid, title, sport, comp, kickoff, status, expected, actual, now):
    try:
        duck.execute(
            """INSERT INTO shared_analytics.live_events
               (event_id, tenant_id, event_name, sport, competition, kickoff_time,
                status, expected_viewers, peak_viewers, pre_scale_done, metrics, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [f"EVT-{uuid4().hex[:10]}", tid, title, sport, comp, kickoff.isoformat(),
             status, expected, actual, status != "scheduled",
             json.dumps({"drm_status": "healthy"}), now.isoformat()],
        )
    except Exception:
        pass
