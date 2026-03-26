"""API Logs generator — 280K req/day normal, 2.8M on ElClasico.

Output: api_logs/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
    is_anomaly_active,
)
from apps.mock_data_gen.generators.medianova.generator import HOURLY_WEIGHTS

logger = structlog.get_logger(__name__)

NORMAL_WEEKDAY_VOLUME = 280_000
NORMAL_WEEKEND_VOLUME = 450_000
HOLIDAY_VOLUME = 170_000

# Endpoint distribution (normal)
ENDPOINT_WEIGHTS: dict[str, float] = {
    "/auth/token/refresh": 0.43,
    "/subscription/check": 0.28,
    "/content/stream": 0.18,
    "/auth/login": 0.05,
    "/epg/schedule": 0.03,
    "/content/search": 0.02,
    "/content/detail": 0.002,
    "/auth/logout": 0.001,
    "/subscription/upgrade": 0.001,
    "/subscription/cancel": 0.001,
    "/epg/now-playing": 0.002,
    "/user/profile": 0.002,
    "/user/preferences": 0.001,
}

ENDPOINT_METHODS: dict[str, str] = {
    "/auth/login": "POST",
    "/auth/token/refresh": "POST",
    "/auth/logout": "POST",
    "/content/stream": "GET",
    "/content/search": "GET",
    "/content/detail": "GET",
    "/subscription/check": "GET",
    "/subscription/upgrade": "POST",
    "/subscription/cancel": "POST",
    "/epg/schedule": "GET",
    "/epg/now-playing": "GET",
    "/user/profile": "GET",
    "/user/preferences": "POST",
}

# Response time ranges per endpoint (ms)
RESPONSE_TIMES: dict[str, tuple[int, int]] = {
    "/auth/login": (150, 300),
    "/auth/token/refresh": (30, 80),
    "/auth/logout": (20, 50),
    "/content/stream": (80, 200),
    "/content/search": (100, 250),
    "/content/detail": (40, 120),
    "/subscription/check": (50, 120),
    "/subscription/upgrade": (200, 500),
    "/subscription/cancel": (200, 500),
    "/epg/schedule": (30, 80),
    "/epg/now-playing": (20, 60),
    "/user/profile": (40, 100),
    "/user/preferences": (50, 120),
}

# Status code distributions
STATUS_NORMAL: dict[int, float] = {200: 0.94, 401: 0.02, 403: 0.01, 404: 0.01, 429: 0.01, 500: 0.005, 502: 0.003, 503: 0.002}

# Error mappings
ERROR_MAP: dict[int, tuple[str, str]] = {
    401: ("AUTH_TOKEN_EXPIRED", "Authentication token expired"),
    403: ("STREAM_403", "Access forbidden — subscription required"),
    404: ("NOT_FOUND", "Resource not found"),
    429: ("RATE_LIMITED", "Too many requests — rate limit exceeded"),
    500: ("INTERNAL_ERROR", "Internal server error"),
    502: ("BAD_GATEWAY", "Bad gateway — upstream error"),
    503: ("CDN_UNAVAILABLE", "Service temporarily unavailable"),
}

APP_VERSIONS = ["3.2.0", "3.2.1", "3.3.0"]
ISPS = ["Turk Telekom", "Turkcell Superonline", "Vodafone Net", "TurkNet"]


class APILogsGenerator(BaseGenerator):
    """Generates API gateway access logs."""

    @property
    def source_name(self) -> str:
        return "api_logs"

    def _pick_weighted(self, options: dict) -> str:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _pick_status(self, endpoint: str, hour_utc: int, multiplier: float,
                     anomaly: str | None, ts: datetime) -> int:
        # CDN outage: /content/stream → 503 dominant
        if anomaly == "cdn_outage" and endpoint == "/content/stream":
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                return self.rng.choices([503, 200], weights=[0.85, 0.15], k=1)[0]

        # Derby peak: rate limiting on /content/stream
        if multiplier >= 2.5 and 18 <= hour_utc <= 21 and endpoint == "/content/stream":
            return self.rng.choices(
                [200, 429, 503, 500],
                weights=[0.88, 0.08, 0.02, 0.02], k=1,
            )[0]

        keys = list(STATUS_NORMAL.keys())
        weights = list(STATUS_NORMAL.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _get_response_time(self, endpoint: str, status: int, multiplier: float,
                           anomaly: str | None) -> int:
        lo, hi = RESPONSE_TIMES.get(endpoint, (50, 150))

        # Derby: 2-3x
        if multiplier >= 2.5:
            lo = int(lo * 2)
            hi = int(hi * 3)

        # CDN outage timeout
        if anomaly == "cdn_outage" and status == 503 and endpoint == "/content/stream":
            return 5000

        # Error responses tend to be faster (rejected early) or timeout
        if status >= 500:
            return self.rng.randint(hi, hi * 3)

        return self.rng.randint(lo, hi)

    def generate_day(self, target_date: date) -> int:
        """Generate all API logs for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)

        is_weekend = target_date.weekday() >= 5
        if anomaly == "holiday":
            base_volume = HOLIDAY_VOLUME
        elif is_weekend:
            base_volume = NORMAL_WEEKEND_VOLUME
        else:
            base_volume = NORMAL_WEEKDAY_VOLUME

        daily_volume = int(base_volume * multiplier)
        total_weight = sum(HOURLY_WEIGHTS)

        all_records: list[dict] = []

        for hour in range(24):
            hw = HOURLY_WEIGHTS[hour] / total_weight
            hourly_volume = max(1, int(daily_volume * hw))

            for _ in range(hourly_volume):
                endpoint = self._pick_weighted(ENDPOINT_WEIGHTS)
                sec = self.rng.randint(0, 3599)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, sec // 60, sec % 60, tzinfo=timezone.utc,
                )

                status = self._pick_status(endpoint, hour, multiplier, anomaly, ts)
                resp_time = self._get_response_time(endpoint, status, multiplier, anomaly)

                sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]
                is_authed = endpoint not in ("/auth/login",)
                err = ERROR_MAP.get(status)

                # Cache hit for GET endpoints with 200
                cache_hit = None
                if ENDPOINT_METHODS.get(endpoint) == "GET" and status == 200:
                    cache_hit = self.rng.random() < 0.30  # 30% cache hit

                all_records.append({
                    "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                    "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
                    "request_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                    "endpoint": endpoint,
                    "method": ENDPOINT_METHODS.get(endpoint, "GET"),
                    "status_code": status,
                    "response_time_ms": resp_time,
                    "user_id_hash": hashlib.sha256(sub.user_id.encode()).hexdigest()[:32] if is_authed else None,
                    "subscription_tier": sub.tier if is_authed else None,
                    "device_type": sub.device_type,
                    "app_version": self.rng.choice(APP_VERSIONS),
                    "ip_hash": hashlib.sha256(f"{sub.user_id}_ip".encode()).hexdigest()[:32],
                    "country_code": sub.country if sub.country != "OTHER" else "GB",
                    "error_code": err[0] if err else None,
                    "error_message": err[1] if err else None,
                    "cache_hit": cache_hit,
                })

        # Sort and write to 5-minute files
        all_records.sort(key=lambda r: r["timestamp"])

        buckets: dict[str, list[dict]] = {}
        for rec in all_records:
            ts_clean = rec["timestamp"].replace("Z", "")
            ts_parsed = datetime.fromisoformat(ts_clean)
            minute_bucket = (ts_parsed.minute // 5) * 5
            key = f"{ts_parsed.hour:02d}-{minute_bucket:02d}"
            buckets.setdefault(key, []).append(rec)

        for key, records in buckets.items():
            ts_str = f"{target_date.isoformat()}-{key}"
            self.write_jsonl_gz(
                records,
                target_date.strftime("%Y"),
                target_date.strftime("%m"),
                target_date.strftime("%d"),
                filename=f"{ts_str}.jsonl.gz",
            )

        total = len(all_records)
        logger.info(
            "api_logs_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    APILogsGenerator().generate_all()
