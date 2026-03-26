"""Widevine DRM log generator — 120K events/day normal, 800K derby.

Output: drm_widevine/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz
Only generates events for Widevine devices (android, web_chrome, web_firefox,
android_tv, tizen_os, webos).
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
from apps.mock_data_gen.generators.medianova.generator import CHANNELS, HOURLY_WEIGHTS

logger = structlog.get_logger(__name__)

WIDEVINE_DEVICES = ("android", "web_chrome", "web_firefox", "android_tv", "tizen_os", "webos")

NORMAL_DAILY_EVENTS = 120_000

# Security level distribution per device
SECURITY_LEVELS: dict[str, dict[str, float]] = {
    "android": {"L1": 0.70, "L2": 0.05, "L3": 0.25},
    "web_chrome": {"L3": 1.0},
    "web_firefox": {"L3": 1.0},
    "android_tv": {"L1": 0.80, "L3": 0.20},
    "tizen_os": {"L3": 1.0},
    "webos": {"L3": 1.0},
}

# Status distributions
STATUS_NORMAL = {"success": 0.992, "failed": 0.003, "timeout": 0.003, "rejected": 0.002}
STATUS_DERBY_PEAK = {"success": 0.88, "timeout": 0.08, "failed": 0.03, "rejected": 0.01}
STATUS_CDN_OUTAGE = {"success": 0.72, "timeout": 0.20, "failed": 0.08}

# OS versions
OS_VERSIONS: dict[str, list[str]] = {
    "android": ["Android 12", "Android 13", "Android 14"],
    "android_tv": ["Android TV 12", "Android TV 13"],
    "tizen_os": ["Tizen 6.5", "Tizen 7.0"],
    "webos": ["webOS 6.0", "webOS 23"],
    "web_chrome": [None],  # type: ignore[list-item]
    "web_firefox": [None],  # type: ignore[list-item]
}

BROWSERS: dict[str, list[str]] = {
    "web_chrome": ["Chrome 120", "Chrome 121", "Chrome 122"],
    "web_firefox": ["Firefox 121", "Firefox 122"],
}

APP_VERSIONS = ["3.2.0", "3.2.1", "3.3.0"]

ISPS = ["Turk Telekom", "Turkcell Superonline", "Vodafone Net", "TurkNet"]

ERROR_CODES = {
    "failed": ("WV_LICENSE_DENIED", "License request denied by policy"),
    "timeout": ("WV_TIMEOUT_5003", "DRM server response timeout"),
    "rejected": ("WV_SERVER_ERROR", "Internal DRM server error"),
}


class WidevineGenerator(BaseGenerator):
    """Generates Widevine DRM license server logs."""

    @property
    def source_name(self) -> str:
        return "drm_widevine"

    def _pick_weighted(self, options: dict) -> str:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _get_status(self, hour_utc: int, multiplier: float, anomaly: str | None,
                    ts: datetime) -> str:
        if anomaly == "cdn_outage":
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                return self._pick_weighted(STATUS_CDN_OUTAGE)
        if multiplier >= 2.5 and 17 <= hour_utc <= 20:
            return self._pick_weighted(STATUS_DERBY_PEAK)
        return self._pick_weighted(STATUS_NORMAL)

    def _get_response_time(self, status: str, multiplier: float) -> int:
        if status == "success":
            return self.rng.randint(80, 150)
        if status == "timeout":
            if multiplier >= 2.5:
                return self.rng.randint(3000, 5000)
            return self.rng.randint(2000, 4000)
        if status == "failed":
            return self.rng.randint(50, 300)
        return self.rng.randint(100, 500)  # rejected

    def _generate_session_events(
        self, session_start: datetime, hour_utc: int, multiplier: float,
        anomaly: str | None,
    ) -> list[dict]:
        """Generate a chain of DRM events for a single streaming session."""
        sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]

        # Only Widevine devices
        if sub.device_type not in WIDEVINE_DEVICES:
            # Re-pick from pool until we get a widevine device
            for _ in range(20):
                sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]
                if sub.device_type in WIDEVINE_DEVICES:
                    break
            else:
                return []

        session_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        content_type = self.rng.choices(["live", "vod"], weights=[0.7, 0.3], k=1)[0]
        channel = self.rng.choice(CHANNELS) if content_type == "live" else None
        content_id = f"cnt_{self.rng.randint(1000, 9999)}"

        security_level = self._pick_weighted(SECURITY_LEVELS[sub.device_type])

        os_ver = self.rng.choice(OS_VERSIONS.get(sub.device_type, [None]))
        browser = self.rng.choice(BROWSERS.get(sub.device_type, [None]))
        app_ver = self.rng.choice(APP_VERSIONS) if sub.device_type in ("android", "android_tv") else None

        ip_hash = hashlib.sha256(f"{sub.user_id}_ip".encode()).hexdigest()[:32]
        pssh = hashlib.sha256(f"pssh_{content_id}".encode()).hexdigest()[:32]

        # Common fields
        base = {
            "drm_server": "drm.ssport.com.tr",
            "session_id": session_id,
            "device_id_hash": sub.device_id,
            "user_id_hash": hashlib.sha256(sub.user_id.encode()).hexdigest()[:32],
            "subscription_tier": sub.tier,
            "content_id": content_id,
            "content_type": content_type,
            "channel": channel,
            "pssh_data": pssh,
            "device_type": sub.device_type,
            "widevine_security_level": security_level,
            "os_version": os_ver,
            "browser": browser,
            "app_version": app_ver,
            "license_type": "streaming",
            "license_duration_s": 600,
            "renewal_interval_s": 300,
            "policy_name": f"policy_{sub.tier}",
            "country_code": sub.country if sub.country != "OTHER" else "GB",
            "isp": self.rng.choice(ISPS),
            "ip_hash": ip_hash,
        }

        events: list[dict] = []
        ts = session_start

        # 1. license_request
        status = self._get_status(hour_utc, multiplier, anomaly, ts)
        error_info = ERROR_CODES.get(status)
        events.append({
            **base,
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "license_request",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "status": status,
            "response_time_ms": self._get_response_time(status, multiplier),
            "error_code": error_info[0] if error_info else None,
            "error_message": error_info[1] if error_info else None,
            "retry_count": 0,
        })

        # If initial request failed, maybe one retry then stop
        if status != "success":
            retry_ts = ts + timedelta(seconds=self.rng.randint(2, 10))
            retry_status = self._get_status(hour_utc, multiplier, anomaly, retry_ts)
            retry_err = ERROR_CODES.get(retry_status)
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "license_request",
                "timestamp": retry_ts.replace(tzinfo=None).isoformat() + "Z",
                "status": retry_status,
                "response_time_ms": self._get_response_time(retry_status, multiplier),
                "error_code": retry_err[0] if retry_err else None,
                "error_message": retry_err[1] if retry_err else None,
                "retry_count": 1,
            })
            if retry_status != "success":
                return events

        # 2. license_renewal (every 300s, session 10-60 min)
        session_duration_s = self.rng.randint(600, 3600)
        num_renewals = session_duration_s // 300
        for i in range(num_renewals):
            renewal_ts = ts + timedelta(seconds=300 * (i + 1))
            if renewal_ts.hour != hour_utc:
                break  # stay within the hour
            r_status = self._get_status(renewal_ts.hour, multiplier, anomaly, renewal_ts)
            r_err = ERROR_CODES.get(r_status)
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "license_renewal",
                "timestamp": renewal_ts.replace(tzinfo=None).isoformat() + "Z",
                "status": r_status,
                "response_time_ms": self._get_response_time(r_status, multiplier),
                "error_code": r_err[0] if r_err else None,
                "error_message": r_err[1] if r_err else None,
                "retry_count": 0,
            })

        # 3. license_validation (30% chance)
        if self.rng.random() < 0.30:
            val_ts = ts + timedelta(seconds=self.rng.randint(60, 300))
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "license_validation",
                "timestamp": val_ts.replace(tzinfo=None).isoformat() + "Z",
                "status": "success",
                "response_time_ms": self.rng.randint(20, 80),
                "error_code": None,
                "error_message": None,
                "retry_count": 0,
            })

        return events

    def generate_day(self, target_date: date) -> int:
        """Generate all Widevine DRM events for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)
        daily_target = int(NORMAL_DAILY_EVENTS * multiplier)
        total_weight = sum(HOURLY_WEIGHTS)

        all_events: list[dict] = []

        for hour in range(24):
            hw = HOURLY_WEIGHTS[hour] / total_weight
            hourly_target = max(1, int(daily_target * hw))

            # Each session produces ~4-8 events on average
            sessions_needed = max(1, hourly_target // 6)
            hour_events: list[dict] = []

            for _ in range(sessions_needed):
                sec = self.rng.randint(0, 3599)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, sec // 60, sec % 60, tzinfo=timezone.utc,
                )
                session_evts = self._generate_session_events(ts, hour, multiplier, anomaly)
                hour_events.extend(session_evts)

            all_events.extend(hour_events)

        # Sort and write to 5-minute files
        all_events.sort(key=lambda r: r["timestamp"])

        buckets: dict[str, list[dict]] = {}
        for rec in all_events:
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

        total = len(all_events)
        logger.info(
            "widevine_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    WidevineGenerator().generate_all()
