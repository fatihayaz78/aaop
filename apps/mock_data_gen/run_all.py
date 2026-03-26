"""Run all mock data generators sequentially.

Usage:
  python -m apps.mock_data_gen.run_all
  python -m apps.mock_data_gen.run_all --start 2026-03-04 --end 2026-03-04
  python -m apps.mock_data_gen.run_all --sources medianova,drm_widevine
  python -m apps.mock_data_gen.run_all --sources all
"""

from __future__ import annotations

import argparse
import time
from datetime import date

import structlog

from apps.mock_data_gen.generators.api_logs.generator import APILogsGenerator
from apps.mock_data_gen.generators.app_reviews.generator import AppReviewsGenerator
from apps.mock_data_gen.generators.base_generator import PERIOD_END, PERIOD_START
from apps.mock_data_gen.generators.billing.generator import BillingGenerator
from apps.mock_data_gen.generators.crm.generator import CRMGenerator
from apps.mock_data_gen.generators.drm_fairplay.generator import FairPlayGenerator
from apps.mock_data_gen.generators.drm_widevine.generator import WidevineGenerator
from apps.mock_data_gen.generators.epg.generator import EPGGenerator
from apps.mock_data_gen.generators.medianova.generator import MedianovaGenerator
from apps.mock_data_gen.generators.newrelic.generator import NewRelicGenerator
from apps.mock_data_gen.generators.npaw.generator import NPAWGenerator
from apps.mock_data_gen.generators.origin_logs.generator import OriginGenerator
from apps.mock_data_gen.generators.player_events.generator import PlayerEventsGenerator
from apps.mock_data_gen.generators.push_notifications.generator import PushNotificationsGenerator

logger = structlog.get_logger(__name__)

SOURCES: dict[str, type] = {
    "medianova": MedianovaGenerator,
    "origin_logs": OriginGenerator,
    "drm_widevine": WidevineGenerator,
    "drm_fairplay": FairPlayGenerator,
    "player_events": PlayerEventsGenerator,
    "npaw": NPAWGenerator,
    "api_logs": APILogsGenerator,
    "newrelic": NewRelicGenerator,
    "crm": CRMGenerator,
    "epg": EPGGenerator,
    "billing": BillingGenerator,
    "push_notifications": PushNotificationsGenerator,
    "app_reviews": AppReviewsGenerator,
}

SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "medianova": "Medianova CDN",
    "origin_logs": "Origin Server",
    "drm_widevine": "Widevine DRM",
    "drm_fairplay": "FairPlay DRM",
    "player_events": "Player Events",
    "npaw": "NPAW Analytics",
    "api_logs": "API Logs",
    "newrelic": "New Relic APM",
    "crm": "CRM/Subscriber",
    "epg": "EPG",
    "billing": "Billing",
    "push_notifications": "Push Notifications",
    "app_reviews": "App Reviews",
}


def run(
    sources: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, dict]:
    """Run generators and return results summary."""
    start = start_date or PERIOD_START
    end = end_date or PERIOD_END

    selected = sources or list(SOURCES.keys())
    results: dict[str, dict] = {}

    total_start = time.time()

    for name in selected:
        if name not in SOURCES:
            logger.warning("unknown_source", source=name)
            continue

        gen_cls = SOURCES[name]
        gen = gen_cls()

        logger.info("generator_start", source=name, start=start.isoformat(), end=end.isoformat())
        src_start = time.time()

        day_results = gen.generate_range(start, end)

        elapsed = round(time.time() - src_start, 2)
        total_records = sum(day_results.values())
        results[name] = {
            "records": total_records,
            "days": len(day_results),
            "elapsed_s": elapsed,
        }
        logger.info(
            "generator_complete",
            source=name,
            records=total_records,
            days=len(day_results),
            elapsed_s=elapsed,
        )

    total_elapsed = round(time.time() - total_start, 2)
    logger.info(
        "run_all_complete",
        sources=len(results),
        total_elapsed_s=total_elapsed,
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="AAOP Mock Data Generator")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--sources", type=str, default="all", help="Comma-separated source names or 'all'")
    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    sources = None if args.sources == "all" else args.sources.split(",")

    run(sources=sources, start_date=start, end_date=end)


if __name__ == "__main__":
    main()
