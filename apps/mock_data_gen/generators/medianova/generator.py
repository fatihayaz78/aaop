"""Medianova CDN log generator — 50K req/day normal, 500K on derby.

Output: medianova/YYYY/MM/DD/{channel}/{YYYY-MM-DD-HH-MM}.jsonl.gz
Each 5-minute interval produces one file per active channel.
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

logger = structlog.get_logger(__name__)

CHANNELS = ("s_sport_1", "s_sport_2", "s_plus_live_1", "s_plus_live_2",
             "cnn_turk", "trt_spor", "a_spor")

EDGE_NODES_TR = ("ist-01", "ist-02", "ank-01", "izm-01")
EDGE_NODES_EU = ("fra-01",)

# Channel traffic share (relative weights)
CHANNEL_WEIGHTS: dict[str, float] = {
    "s_sport_1": 0.30, "s_sport_2": 0.20, "s_plus_live_1": 0.12,
    "s_plus_live_2": 0.08, "cnn_turk": 0.15, "trt_spor": 0.08, "a_spor": 0.07,
}

# Hourly traffic shape (UTC hours 0-23). Peak = 17-20 UTC (20-23 TR).
HOURLY_WEIGHTS: list[float] = [
    0.8, 0.5, 0.3, 0.2, 0.2, 0.2,   # 00-05 UTC
    0.3, 0.5, 0.8, 1.0, 1.2, 1.5,   # 06-11 UTC
    2.0, 2.5, 3.0, 3.5, 4.0, 5.0,   # 12-17 UTC (15-20 TR)
    5.0, 4.5, 3.5, 2.5, 1.5, 1.0,   # 18-23 UTC (21-02 TR)
]

NORMAL_DAILY_VOLUME = 50_000
BASE_DAILY_VOLUME = NORMAL_DAILY_VOLUME  # before multiplier

# Cache status distributions
CACHE_NORMAL = {"HIT": 0.72, "MISS": 0.18, "BYPASS": 0.05, "EXPIRED": 0.04, "STALE": 0.01}
CACHE_DERBY = {"HIT": 0.55, "MISS": 0.35, "BYPASS": 0.05, "EXPIRED": 0.04, "STALE": 0.01}

# Status code distributions
STATUS_NORMAL = {200: 0.94, 206: 0.03, 304: 0.01, 404: 0.01, 503: 0.005, 502: 0.003, 500: 0.002}
STATUS_OUTAGE = {503: 0.85, 200: 0.15}

# User agent pool
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Tizen 7.0; TV) AppleWebKit/537.36 Chrome/108.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
    "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36",
    "SSportPlus/3.2.1 (Android 13; SM-G998B)",
    "SSportPlus/3.2.1 (iOS 17.2; iPhone15,2)",
    "ExoPlayer/2.19.1 (Linux; Android 13)",
    "AVPlayer/1.0 (Apple TV; tvOS 17.2)",
    "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36",
]

# ISP pool
ISPS_TR = ["Turk Telekom", "Turkcell Superonline", "Vodafone Net", "TurkNet", "Millenicom"]
ISPS_EU = ["Deutsche Telekom", "Vodafone DE", "KPN", "Cyta"]

# Content type pool
CONTENT_TYPES = {
    "hls_segment": "video/MP2T",
    "manifest": "application/vnd.apple.mpegurl",
    "live": "video/MP2T",
    "vod": "video/MP2T",
}

BITRATES = [360, 480, 720, 1080, 1440, 2160]
SSL_CIPHERS = ["ECDHE-RSA-AES128-GCM-SHA256", "ECDHE-RSA-AES256-GCM-SHA384",
               "TLS_AES_128_GCM_SHA256", "TLS_AES_256_GCM_SHA384"]


class MedianovaGenerator(BaseGenerator):
    """Generates Medianova CDN access logs."""

    @property
    def source_name(self) -> str:
        return "medianova"

    def _pick_weighted(self, options: dict, *, as_int: bool = False):
        """Pick a key from weighted dict."""
        keys = list(options.keys())
        weights = list(options.values())
        result = self.rng.choices(keys, weights=weights, k=1)[0]
        return int(result) if as_int else result

    def _get_hourly_volume(self, hour_utc: int, multiplier: float) -> int:
        """Calculate request volume for a specific UTC hour."""
        weight = HOURLY_WEIGHTS[hour_utc]
        total_weight = sum(HOURLY_WEIGHTS)
        hourly_share = weight / total_weight
        daily_volume = int(BASE_DAILY_VOLUME * multiplier)
        return max(1, int(daily_volume * hourly_share))

    def _generate_record(
        self,
        ts: datetime,
        channel: str,
        anomaly: str | None,
    ) -> dict:
        """Generate a single Medianova log record."""
        is_outage = (anomaly == "cdn_outage" and
                     is_anomaly_active(
                         ts.replace(tzinfo=None) + timedelta(hours=3),  # to TR local
                         "cdn_outage"))
        is_derby = self.get_multiplier(ts.date()) >= 2.5

        # Status code
        status_dist = STATUS_OUTAGE if is_outage else STATUS_NORMAL
        status = self._pick_weighted(status_dist, as_int=True)

        # Cache status
        cache_dist = CACHE_DERBY if is_derby else CACHE_NORMAL
        if is_outage:
            cache_status = "MISS"
        else:
            cache_status = self._pick_weighted(cache_dist)

        # Stream type
        stream_type = self.rng.choices(
            ["live", "vod", "hls_segment", "manifest"],
            weights=[0.45, 0.25, 0.20, 0.10], k=1,
        )[0]

        # Request URI
        bitrate = self.rng.choice(BITRATES)
        seg_num = self.rng.randint(1, 9999)
        content_id = self.rng.randint(1000, 9999)
        if stream_type == "manifest":
            uri = f"/live/{channel}/master.m3u8"
        elif stream_type == "live" or stream_type == "hls_segment":
            uri = f"/live/{channel}/{bitrate}/seg_{seg_num}.ts"
        else:
            uri = f"/vod/{content_id}/{bitrate}/seg_{seg_num}.ts"

        # Subscriber info for geo/device
        sub = self.subscriber_pool[self.rng.randint(0, len(self.subscriber_pool) - 1)]

        # Edge node
        if sub.country in ("DE", "NL", "OTHER"):
            edge_node = self.rng.choice(EDGE_NODES_EU)
        else:
            edge_node = self.rng.choice(EDGE_NODES_TR)

        # ISP
        isp = self.rng.choice(ISPS_TR if sub.country == "TR" else ISPS_EU)

        # Upstream response time: only for MISS/EXPIRED/STALE
        upstream_time = None
        if cache_status in ("MISS", "EXPIRED", "STALE"):
            upstream_time = round(self.rng.uniform(0.01, 0.8), 4)
            if is_outage:
                upstream_time = round(self.rng.uniform(1.0, 5.0), 4)

        # Body/bytes
        if stream_type == "manifest":
            body_bytes = self.rng.randint(500, 5000)
        else:
            body_bytes = self.rng.randint(50_000, 2_000_000)
        bytes_sent = body_bytes + self.rng.randint(200, 800)

        # Request time
        if cache_status == "HIT":
            req_time = round(self.rng.uniform(0.001, 0.02), 4)
        else:
            req_time = round(self.rng.uniform(0.01, 1.0), 4)
            if is_outage:
                req_time = round(self.rng.uniform(1.0, 10.0), 4)

        # SSL
        ssl_proto = self.rng.choice(["TLSv1.2", "TLSv1.3"])
        ssl_cipher = self.rng.choice(SSL_CIPHERS)

        # Remote addr hashed
        remote_addr = hashlib.sha256(
            f"{sub.user_id}_{sub.device_id}".encode()
        ).hexdigest()[:32]

        request_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

        return {
            "request_id": request_id,
            "request_method": "GET",
            "request_uri": uri,
            "request_param": None,
            "request_time": req_time,
            "scheme": "https",
            "http_protocol": self.rng.choice(["HTTP/1.1", "HTTP/2.0"]),
            "http_host": f"cdn.ssport.com.tr",
            "http_referrer": None,
            "http_user_agent": self.rng.choice(USER_AGENTS),
            "status": status,
            "content_type": CONTENT_TYPES.get(stream_type, "video/MP2T"),
            "proxy_cache_status": cache_status,
            "body_bytes_sent": body_bytes,
            "bytes_sent": bytes_sent,
            "upstream_response_time": upstream_time,
            "sent_http_content_length": body_bytes if status == 200 else None,
            "via": "1.1 medianova" if cache_status == "HIT" else None,
            "timestamp": ts.isoformat() + "Z",
            "remote_addr": remote_addr,
            "client_port": self.rng.randint(1024, 65535),
            "asn": f"AS{self.rng.randint(9000, 60000)}",
            "country_code": sub.country if sub.country != "OTHER" else "GB",
            "isp": isp,
            "tcp_info_rtt": self.rng.randint(5, 200),
            "tcp_info_rtt_var": self.rng.randint(1, 50),
            "ssl_protocol": ssl_proto,
            "ssl_cipher": ssl_cipher,
            "resource_uuid": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "account_type": "enterprise",
            "channel": channel,
            "edge_node": edge_node,
            "stream_type": stream_type,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate all Medianova CDN logs for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)
        total_records = 0

        for hour in range(24):
            hourly_volume = self._get_hourly_volume(hour, multiplier)

            # Distribute across channels
            for channel in CHANNELS:
                ch_weight = CHANNEL_WEIGHTS[channel]
                ch_volume = max(1, int(hourly_volume * ch_weight))

                # Distribute across 5-minute slots (12 per hour)
                for slot in range(12):
                    minute = slot * 5
                    slot_volume = max(1, ch_volume // 12)
                    if slot == 0:
                        slot_volume += ch_volume % 12  # remainder in first slot

                    records: list[dict] = []
                    for _ in range(slot_volume):
                        # Random second within the 5-min window
                        sec_offset = self.rng.randint(0, 299)
                        ts = datetime(
                            target_date.year, target_date.month, target_date.day,
                            hour, minute, tzinfo=timezone.utc,
                        ) + timedelta(seconds=sec_offset)
                        records.append(self._generate_record(ts, channel, anomaly))

                    # Write 5-minute file
                    ts_str = f"{target_date.isoformat()}-{hour:02d}-{minute:02d}"
                    self.write_jsonl_gz(
                        records,
                        target_date.strftime("%Y"),
                        target_date.strftime("%m"),
                        target_date.strftime("%d"),
                        channel,
                        filename=f"{ts_str}.jsonl.gz",
                    )
                    total_records += len(records)

        logger.info(
            "medianova_day_complete",
            date=target_date.isoformat(),
            records=total_records,
            multiplier=multiplier,
        )
        return total_records


if __name__ == "__main__":
    MedianovaGenerator().generate_all()
