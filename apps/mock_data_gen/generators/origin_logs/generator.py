"""Origin Server log generator — correlated with Medianova CDN MISS events.

Output: origin_logs/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
    is_anomaly_active,
)
from apps.mock_data_gen.generators.medianova.generator import (
    CHANNELS,
    EDGE_NODES_TR,
    HOURLY_WEIGHTS,
    NORMAL_DAILY_VOLUME,
    CACHE_NORMAL,
    CACHE_DERBY,
)

logger = structlog.get_logger(__name__)

ORIGIN_HOSTS = ("origin-1.ssport.com.tr", "origin-2.ssport.com.tr")
ENCODER_IDS = ("enc-01", "enc-02", "enc-03")
BITRATES = [360, 480, 720, 1080, 1440, 2160]
OUTPUT_PROFILES = ["360p", "480p", "720p", "1080p"]


class OriginGenerator(BaseGenerator):
    """Generates Origin Server logs correlated with Medianova MISS events."""

    @property
    def source_name(self) -> str:
        return "origin_logs"

    def _get_origin_load(self, hour_utc: int, multiplier: float, anomaly: str | None,
                         ts: datetime | None = None) -> float:
        """Calculate origin load percentage based on conditions."""
        base = self.rng.uniform(20, 45)

        # Peak hours (17-20 UTC = 20-23 TR)
        if 17 <= hour_utc <= 20:
            base += 10

        if multiplier >= 2.5:
            # Derby peak
            if 17 <= hour_utc <= 20:
                return self.rng.uniform(75, 95)
            return self.rng.uniform(50, 75)

        if anomaly == "cdn_outage" and ts is not None:
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                return self.rng.uniform(85, 98)

        return round(base, 1)

    def _gen_cdn_miss(self, ts: datetime, hour_utc: int, multiplier: float,
                      anomaly: str | None) -> dict:
        """Generate a cdn_miss event (correlated with Medianova MISS)."""
        origin_host = self.rng.choice(ORIGIN_HOSTS)
        channel = self.rng.choice(CHANNELS)
        bitrate = self.rng.choice(BITRATES)
        seg_num = self.rng.randint(1, 9999)
        uri = f"/live/{channel}/{bitrate}/seg_{seg_num}.ts"
        edge = self.rng.choice(EDGE_NODES_TR)

        load = self._get_origin_load(hour_utc, multiplier, anomaly, ts)
        resp_time = self.rng.randint(10, 200)
        if load > 80:
            resp_time = self.rng.randint(200, 2000)

        status = 200
        if anomaly == "cdn_outage":
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                status = self.rng.choices([503, 200], weights=[0.7, 0.3], k=1)[0]

        # Deterministic request_id based on seed state (same seed → same IDs)
        req_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "cdn_miss",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "origin_host": origin_host,
            "request_method": "GET",
            "request_uri": uri,
            "http_protocol": "HTTP/1.1",
            "cdn_pop": edge,
            "medianova_req_id": req_id,
            "status_code": status,
            "response_time_ms": resp_time,
            "bytes_sent": self.rng.randint(50_000, 2_000_000),
            "cache_control_header": f"max-age={self.rng.choice([60, 120, 300, 600])}",
            "origin_load_pct": round(load, 1),
            "channel": channel,
            "stream_type": "live",
            "manifest_type": None,
            "segment_number": seg_num,
            "bitrate_kbps": bitrate,
            "duration_ms": self.rng.choice([2000, 4000, 6000]),
            "health_status": None,
            "check_source": None,
            "latency_ms": None,
            "encoder_id": None,
            "input_stream": None,
            "output_profiles": None,
            "transcoder_status": None,
            "error_message": None,
            "keyframe_interval_ms": None,
        }

    def _gen_hls_fetch(self, ts: datetime, hour_utc: int, multiplier: float,
                       anomaly: str | None) -> dict:
        """Generate an hls_dash_fetch event."""
        origin_host = self.rng.choice(ORIGIN_HOSTS)
        channel = self.rng.choice(CHANNELS)
        manifest = self.rng.choice(["hls_master", "hls_media", "dash_mpd", "segment"])

        if manifest == "segment":
            uri = f"/live/{channel}/{self.rng.choice(BITRATES)}/seg_{self.rng.randint(1, 9999)}.ts"
        elif manifest == "hls_master":
            uri = f"/live/{channel}/master.m3u8"
        elif manifest == "hls_media":
            uri = f"/live/{channel}/{self.rng.choice(BITRATES)}/media.m3u8"
        else:
            uri = f"/live/{channel}/manifest.mpd"

        load = self._get_origin_load(hour_utc, multiplier, anomaly, ts)

        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "hls_dash_fetch",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "origin_host": origin_host,
            "request_method": "GET",
            "request_uri": uri,
            "http_protocol": "HTTP/1.1",
            "cdn_pop": self.rng.choice(EDGE_NODES_TR),
            "medianova_req_id": None,
            "status_code": 200,
            "response_time_ms": self.rng.randint(5, 100),
            "bytes_sent": self.rng.randint(500, 50_000),
            "cache_control_header": "no-cache",
            "origin_load_pct": round(load, 1),
            "channel": channel,
            "stream_type": "live",
            "manifest_type": manifest,
            "segment_number": self.rng.randint(1, 9999) if manifest == "segment" else None,
            "bitrate_kbps": self.rng.choice(BITRATES) if manifest == "segment" else None,
            "duration_ms": self.rng.choice([2000, 4000]) if manifest == "segment" else None,
            "health_status": None,
            "check_source": None,
            "latency_ms": None,
            "encoder_id": None,
            "input_stream": None,
            "output_profiles": None,
            "transcoder_status": None,
            "error_message": None,
            "keyframe_interval_ms": None,
        }

    def _gen_health_check(self, ts: datetime, origin_host: str, hour_utc: int,
                          multiplier: float, anomaly: str | None) -> dict:
        """Generate a health_check event."""
        # Determine health status
        if anomaly == "cdn_outage":
            tr_time = ts.replace(tzinfo=None) + timedelta(hours=3)
            if is_anomaly_active(tr_time, "cdn_outage"):
                status = self.rng.choices(
                    ["unhealthy", "degraded", "healthy"],
                    weights=[0.80, 0.15, 0.05], k=1,
                )[0]
            else:
                status = self.rng.choices(
                    ["healthy", "degraded"], weights=[0.95, 0.05], k=1,
                )[0]
        elif multiplier >= 2.5 and 17 <= hour_utc <= 20:
            status = self.rng.choices(
                ["healthy", "degraded", "unhealthy"],
                weights=[0.50, 0.40, 0.10], k=1,
            )[0]
        else:
            status = self.rng.choices(
                ["healthy", "degraded"], weights=[0.95, 0.05], k=1,
            )[0]

        latency = self.rng.randint(1, 10)
        if status == "degraded":
            latency = self.rng.randint(50, 200)
        elif status == "unhealthy":
            latency = self.rng.randint(500, 5000)

        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "health_check",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "origin_host": origin_host,
            "request_method": None,
            "request_uri": None,
            "http_protocol": None,
            "cdn_pop": None,
            "medianova_req_id": None,
            "status_code": None,
            "response_time_ms": None,
            "bytes_sent": None,
            "cache_control_header": None,
            "origin_load_pct": None,
            "channel": None,
            "stream_type": None,
            "manifest_type": None,
            "segment_number": None,
            "bitrate_kbps": None,
            "duration_ms": None,
            "health_status": status,
            "check_source": self.rng.choice(["medianova", "internal"]),
            "latency_ms": latency,
            "encoder_id": None,
            "input_stream": None,
            "output_profiles": None,
            "transcoder_status": None,
            "error_message": None,
            "keyframe_interval_ms": None,
        }

    def _gen_transcoder_event(self, ts: datetime, channel: str,
                              status: str, hour_utc: int, multiplier: float,
                              anomaly: str | None) -> dict:
        """Generate a transcoder_event."""
        encoder = self.rng.choice(ENCODER_IDS)
        error_msg = None
        if status == "error":
            load = self._get_origin_load(hour_utc, multiplier, anomaly, ts)
            error_msg = f"CPU overload ({load:.0f}%)" if load > 90 else "Keyframe sync failure"

        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "transcoder_event",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "origin_host": self.rng.choice(ORIGIN_HOSTS),
            "request_method": None,
            "request_uri": None,
            "http_protocol": None,
            "cdn_pop": None,
            "medianova_req_id": None,
            "status_code": None,
            "response_time_ms": None,
            "bytes_sent": None,
            "cache_control_header": None,
            "origin_load_pct": None,
            "channel": channel,
            "stream_type": "live",
            "manifest_type": None,
            "segment_number": None,
            "bitrate_kbps": None,
            "duration_ms": None,
            "health_status": None,
            "check_source": None,
            "latency_ms": None,
            "encoder_id": encoder,
            "input_stream": f"rtmp://ingest.ssport.com.tr/live/{channel}",
            "output_profiles": OUTPUT_PROFILES,
            "transcoder_status": status,
            "error_message": error_msg,
            "keyframe_interval_ms": 2000,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate all Origin Server logs for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)
        all_records: list[dict] = []

        # ── cdn_miss events ──
        # Proportional to Medianova MISS rate
        miss_rate = CACHE_DERBY["MISS"] if multiplier >= 2.5 else CACHE_NORMAL["MISS"]
        daily_miss_count = int(NORMAL_DAILY_VOLUME * multiplier * miss_rate)

        for hour in range(24):
            hw = HOURLY_WEIGHTS[hour] / sum(HOURLY_WEIGHTS)
            hourly_miss = max(1, int(daily_miss_count * hw))

            for _ in range(hourly_miss):
                sec = self.rng.randint(0, 3599)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, sec // 60, sec % 60, tzinfo=timezone.utc,
                )
                all_records.append(self._gen_cdn_miss(ts, hour, multiplier, anomaly))

        # ── hls_dash_fetch events ── (cdn_miss × 1.3)
        hls_count = int(daily_miss_count * 1.3)
        for hour in range(24):
            hw = HOURLY_WEIGHTS[hour] / sum(HOURLY_WEIGHTS)
            hourly_hls = max(1, int(hls_count * hw))

            for _ in range(hourly_hls):
                sec = self.rng.randint(0, 3599)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, sec // 60, sec % 60, tzinfo=timezone.utc,
                )
                all_records.append(self._gen_hls_fetch(ts, hour, multiplier, anomaly))

        # ── health_check events ── (every 30s, 2 hosts = 2880/day)
        for origin_host in ORIGIN_HOSTS:
            ts = datetime(
                target_date.year, target_date.month, target_date.day,
                0, 0, 0, tzinfo=timezone.utc,
            )
            end = ts + timedelta(days=1)
            while ts < end:
                all_records.append(
                    self._gen_health_check(ts, origin_host, ts.hour, multiplier, anomaly)
                )
                ts += timedelta(seconds=30)

        # ── transcoder_event ── (started at day begin + periodic running)
        for channel in CHANNELS:
            # Day-start "started" event
            start_ts = datetime(
                target_date.year, target_date.month, target_date.day,
                0, 0, 1, tzinfo=timezone.utc,
            )
            all_records.append(
                self._gen_transcoder_event(start_ts, channel, "started", 0, multiplier, anomaly)
            )

            # Periodic "running" events every hour
            for hour in range(24):
                run_ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    hour, 30, 0, tzinfo=timezone.utc,
                )
                all_records.append(
                    self._gen_transcoder_event(run_ts, channel, "running", hour, multiplier, anomaly)
                )

            # Derby: add error events during peak
            if multiplier >= 2.5:
                for hour in [18, 19, 20]:
                    err_ts = datetime(
                        target_date.year, target_date.month, target_date.day,
                        hour, self.rng.randint(0, 59), 0, tzinfo=timezone.utc,
                    )
                    all_records.append(
                        self._gen_transcoder_event(err_ts, channel, "error", hour, multiplier, anomaly)
                    )

        # Sort by timestamp and write to 5-minute files
        all_records.sort(key=lambda r: r["timestamp"])

        # Group into 5-minute buckets
        buckets: dict[str, list[dict]] = {}
        for rec in all_records:
            ts_str_clean = rec["timestamp"].replace("Z", "").replace("+00:00", "")
            ts_parsed = datetime.fromisoformat(ts_str_clean)
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
            "origin_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    OriginGenerator().generate_all()
