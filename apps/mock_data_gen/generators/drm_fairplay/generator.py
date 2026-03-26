"""FairPlay DRM log generator — Apple devices only, ~55K events/day normal.

Output: drm_fairplay/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz
Handles March 15 certificate expiry anomaly (ios/apple_tv affected,
web_safari unaffected).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
)
from apps.mock_data_gen.generators.medianova.generator import CHANNELS, HOURLY_WEIGHTS

logger = structlog.get_logger(__name__)

FAIRPLAY_DEVICES = ("ios", "apple_tv", "web_safari")

NORMAL_DAILY_EVENTS = 55_000

# Device models
DEVICE_MODELS: dict[str, list[str]] = {
    "ios": ["iPhone 13", "iPhone 14", "iPhone 14 Pro", "iPhone 15", "iPhone 15 Pro",
            "iPad Air", "iPad Pro"],
    "apple_tv": ["Apple TV 4K (3rd gen)", "Apple TV 4K (2nd gen)"],
    "web_safari": ["MacBook Pro", "MacBook Air", "iMac"],
}

IOS_VERSIONS = ["iOS 16.7", "iOS 17.0", "iOS 17.1", "iOS 17.2"]
TVOS_VERSIONS = ["tvOS 17.0", "tvOS 17.1", "tvOS 17.2"]
SAFARI_VERSIONS = ["Safari 17.0", "Safari 17.1", "Safari 17.2"]
APP_VERSIONS = ["3.2.0", "3.2.1", "3.3.0"]

# Status distributions
STATUS_NORMAL = {"success": 0.993, "failed": 0.004, "timeout": 0.003}
STATUS_CERT_EXPIRED = {"failed": 0.95, "timeout": 0.05}

ISPS = ["Turk Telekom", "Turkcell Superonline", "Vodafone Net", "TurkNet"]

ERROR_CODES_NORMAL = {
    "failed": ("FP_LICENSE_DENIED", "FairPlay license request denied"),
    "timeout": ("FP_TIMEOUT_5003", "FairPlay server response timeout"),
}


class FairPlayGenerator(BaseGenerator):
    """Generates FairPlay DRM license server logs for Apple devices."""

    @property
    def source_name(self) -> str:
        return "drm_fairplay"

    def _pick_weighted(self, options: dict) -> str:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _is_cert_expired(self, ts: datetime, device_type: str, anomaly: str | None) -> bool:
        """Check if FairPlay cert is expired at this timestamp.

        March 15 09:00-18:00 UTC: expired for ios/apple_tv.
        web_safari is NEVER affected (different cert chain).
        """
        if anomaly != "fairplay_cert_expired":
            return False
        if device_type == "web_safari":
            return False
        hour = ts.hour
        return 9 <= hour < 18

    def _generate_session_events(
        self, session_start: datetime, hour_utc: int, multiplier: float,
        anomaly: str | None,
    ) -> list[dict]:
        """Generate a chain of FairPlay DRM events for a single session."""
        sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]

        # Only FairPlay devices
        if sub.device_type not in FAIRPLAY_DEVICES:
            for _ in range(30):
                sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]
                if sub.device_type in FAIRPLAY_DEVICES:
                    break
            else:
                return []

        session_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        content_type = self.rng.choices(["live", "vod"], weights=[0.7, 0.3], k=1)[0]
        channel = self.rng.choice(CHANNELS) if content_type == "live" else None
        content_id = f"cnt_{self.rng.randint(1000, 9999)}"

        ip_hash = hashlib.sha256(f"{sub.user_id}_ip".encode()).hexdigest()[:32]
        pssh = hashlib.sha256(f"pssh_{content_id}".encode()).hexdigest()[:32]
        key_id = hashlib.sha256(f"fpkey_{content_id}".encode()).hexdigest()[:32]

        # Device-specific fields
        ios_ver = self.rng.choice(IOS_VERSIONS) if sub.device_type == "ios" else None
        tvos_ver = self.rng.choice(TVOS_VERSIONS) if sub.device_type == "apple_tv" else None
        safari_ver = self.rng.choice(SAFARI_VERSIONS) if sub.device_type == "web_safari" else None
        model = self.rng.choice(DEVICE_MODELS[sub.device_type])
        app_ver = self.rng.choice(APP_VERSIONS) if sub.device_type in ("ios", "apple_tv") else None

        cert_expired = self._is_cert_expired(session_start, sub.device_type, anomaly)

        # Certificate fields
        cert_status = "expired" if cert_expired else "valid"
        cert_expiry = "2026-03-14T23:59:59Z" if cert_expired else "2027-03-15T23:59:59Z"
        ksm_code = 403 if cert_expired else 200

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
            "ios_version": ios_ver,
            "tvos_version": tvos_ver,
            "safari_version": safari_ver,
            "device_model": model,
            "app_version": app_ver,
            "certificate_status": cert_status,
            "certificate_expiry": cert_expiry,
            "fairplay_key_id": key_id,
            "ksm_response_code": ksm_code,
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
        if cert_expired:
            status = self._pick_weighted(STATUS_CERT_EXPIRED)
            error_code = "FP_CERT_EXPIRED_4031"
            error_message = "FairPlay certificate expired — KSM rejected"
            resp_time = self.rng.randint(50, 200)
            retry_count = self.rng.randint(2, 4)
        else:
            status = self._pick_weighted(STATUS_NORMAL)
            err_info = ERROR_CODES_NORMAL.get(status)
            error_code = err_info[0] if err_info else None
            error_message = err_info[1] if err_info else None
            resp_time = self.rng.randint(90, 160) if status == "success" else self.rng.randint(200, 3000)
            retry_count = 0

        events.append({
            **base,
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "license_request",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "status": status,
            "response_time_ms": resp_time,
            "error_code": error_code,
            "error_message": error_message,
            "retry_count": retry_count,
        })

        # If cert expired or failed, session stops
        if cert_expired or status != "success":
            return events

        # 2. license_renewal (every 300s)
        session_duration_s = self.rng.randint(600, 3600)
        num_renewals = session_duration_s // 300
        for i in range(num_renewals):
            renewal_ts = ts + timedelta(seconds=300 * (i + 1))
            if renewal_ts.hour != hour_utc:
                break
            r_status = self._pick_weighted(STATUS_NORMAL)
            r_err = ERROR_CODES_NORMAL.get(r_status)
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "license_renewal",
                "timestamp": renewal_ts.replace(tzinfo=None).isoformat() + "Z",
                "status": r_status,
                "response_time_ms": self.rng.randint(90, 160) if r_status == "success" else self.rng.randint(200, 3000),
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
        """Generate all FairPlay DRM events for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)
        daily_target = int(NORMAL_DAILY_EVENTS * multiplier)
        total_weight = sum(HOURLY_WEIGHTS)

        all_events: list[dict] = []

        for hour in range(24):
            hw = HOURLY_WEIGHTS[hour] / total_weight
            hourly_target = max(1, int(daily_target * hw))
            sessions_needed = max(1, hourly_target // 5)

            for _ in range(sessions_needed):
                sec = self.rng.randint(0, 3599)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, sec // 60, sec % 60, tzinfo=timezone.utc,
                )
                session_evts = self._generate_session_events(ts, hour, multiplier, anomaly)
                all_events.extend(session_evts)

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
            "fairplay_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    FairPlayGenerator().generate_all()
