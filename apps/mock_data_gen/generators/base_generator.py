"""Base generator — abstract class with JSONL/JSON/CSV output utilities.

All 13 log-source generators extend this class.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import random
from abc import ABC, abstractmethod
from datetime import date, timedelta
from pathlib import Path

import structlog

from apps.mock_data_gen.generators.calendar_events import get_traffic_multiplier
from apps.mock_data_gen.generators.subscriber_pool import SubscriberPool

logger = structlog.get_logger(__name__)

OUTPUT_ROOT = Path("/Users/fatihayaz/Documents/Projects/AAOP/aaop-mock-data")

# Period boundaries
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 3, 31)

SEED = 42


class BaseGenerator(ABC):
    """Abstract base for all 13 log-source generators.

    Subclasses must implement:
        - source_name: str property
        - generate_day(target_date): produce records for one day
    """

    def __init__(self, output_root: Path | None = None, seed: int = SEED) -> None:
        self.output_root = output_root or OUTPUT_ROOT
        self.seed = seed
        self.rng = random.Random(seed)
        self._subscriber_pool: SubscriberPool | None = None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique source identifier (e.g. 'medianova', 'drm_widevine')."""

    @abstractmethod
    def generate_day(self, target_date: date) -> int:
        """Generate all records for a single day. Returns record count."""

    @property
    def subscriber_pool(self) -> SubscriberPool:
        """Lazy-loaded subscriber pool (shared across generators)."""
        if self._subscriber_pool is None:
            self._subscriber_pool = SubscriberPool(seed=self.seed)
        return self._subscriber_pool

    def get_multiplier(self, target_date: date) -> float:
        """Get traffic multiplier for a date from calendar events."""
        return get_traffic_multiplier(target_date)

    def generate_range(self, start: date, end: date) -> dict[str, int]:
        """Generate data for a date range. Returns {date_str: record_count}."""
        results: dict[str, int] = {}
        current = start
        while current <= end:
            count = self.generate_day(current)
            results[current.isoformat()] = count
            logger.info(
                "day_generated",
                source=self.source_name,
                date=current.isoformat(),
                records=count,
                multiplier=self.get_multiplier(current),
            )
            current += timedelta(days=1)
        return results

    def generate_all(self) -> dict[str, int]:
        """Generate the full 91-day period."""
        return self.generate_range(PERIOD_START, PERIOD_END)

    # ── Output helpers ──

    def _output_dir(self, *parts: str) -> Path:
        """Create and return output directory under source_name."""
        path = self.output_root / self.source_name / Path(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_jsonl_gz(
        self,
        records: list[dict],
        *path_parts: str,
        filename: str,
    ) -> Path:
        """Write records as gzipped JSONL. Returns the output path."""
        out_dir = self._output_dir(*path_parts)
        out_path = out_dir / filename

        buf = io.BytesIO()
        with gzip.open(buf, "wt", encoding="utf-8") as gz:
            for record in records:
                gz.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        out_path.write_bytes(buf.getvalue())
        return out_path

    def write_json(
        self,
        data: dict | list,
        *path_parts: str,
        filename: str,
    ) -> Path:
        """Write data as a single JSON file. Returns the output path."""
        out_dir = self._output_dir(*path_parts)
        out_path = out_dir / filename
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return out_path

    def write_csv(
        self,
        records: list[dict],
        *path_parts: str,
        filename: str,
        fieldnames: list[str] | None = None,
    ) -> Path:
        """Write records as CSV. Returns the output path."""
        out_dir = self._output_dir(*path_parts)
        out_path = out_dir / filename

        if not records:
            out_path.write_text("", encoding="utf-8")
            return out_path

        fields = fieldnames or list(records[0].keys())

        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)

        return out_path

    @staticmethod
    def iter_dates(start: date, end: date):
        """Yield each date in [start, end] range."""
        current = start
        while current <= end:
            yield current
            current += timedelta(days=1)
