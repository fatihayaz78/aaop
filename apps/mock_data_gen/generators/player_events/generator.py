"""Player Events log generator — session-based event chains.

Output: player_events/YYYY/MM/DD/{YYYY-MM-DD-HH-MM}.jsonl.gz
Each session produces: session_start → buffer/bitrate/error/seek → session_end.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import (
    get_anomaly_for_date,
    is_anomaly_active,
)
from apps.mock_data_gen.generators.medianova.generator import CHANNELS, HOURLY_WEIGHTS

logger = structlog.get_logger(__name__)

NORMAL_DAILY_SESSIONS = 50_000

BITRATE_PROFILES = [6000, 4500, 3000, 1500, 900, 450]  # kbps

# Player version by device
PLAYER_VERSIONS: dict[str, str] = {
    "android": "ExoPlayer/2.18.7",
    "android_tv": "ExoPlayer/2.18.7",
    "ios": "AVPlayer/iOS-17.2",
    "apple_tv": "AVPlayer/tvOS-17.2",
    "web_chrome": "HLS.js/1.4.12",
    "web_firefox": "HLS.js/1.4.12",
    "web_safari": "HLS.js/1.4.12",
    "tizen_os": "Shaka/4.3.8",
    "webos": "Shaka/4.3.8",
}

ERROR_CODES = ["EXO_2320", "AVP_1001", "NET_TIMEOUT", "DRM_ERROR"]


@dataclass
class SessionSummary:
    """Summary of a player session — shared with NPAW generator for correlation."""

    session_id: str
    user_id_hash: str
    device_type: str
    subscription_tier: str
    content_id: str
    content_type: str
    channel: str | None
    country_code: str
    cdn_provider: str
    startup_time_ms: int
    total_duration_ms: int
    watched_duration_ms: int
    total_buffering_ms: int
    buffer_ratio: float
    avg_bitrate_kbps: int
    num_bitrate_changes: int
    num_errors: int
    num_seeks: int
    completion_rate: float
    exit_reason: str
    final_qoe_score: float
    session_start_ts: datetime
    player_version: str


def compute_qoe_score(
    buffer_ratio: float,
    startup_time_ms: int,
    error_count: int,
    avg_bitrate_kbps: int,
) -> float:
    """QoE formula: 5.0 - penalties."""
    score = 5.0

    # Buffer penalty
    score -= buffer_ratio * 10

    # Startup penalty
    if startup_time_ms < 1000:
        pass
    elif startup_time_ms < 3000:
        score -= 0.3
    elif startup_time_ms < 5000:
        score -= 0.7
    else:
        score -= 1.2

    # Error penalty
    score -= error_count * 0.3

    # Bitrate penalty
    if avg_bitrate_kbps >= 3000:
        pass
    elif avg_bitrate_kbps >= 1500:
        score -= 0.3
    else:
        score -= 0.7

    return round(max(0.0, min(5.0, score)), 2)


def generate_sessions_for_day(
    rng,
    target_date: date,
    subscriber_pool,
    multiplier: float,
    anomaly: str | None,
) -> list[SessionSummary]:
    """Generate session summaries for a day. Shared between Player & NPAW generators."""
    is_weekend = target_date.weekday() >= 5
    base_sessions = 80_000 if is_weekend else NORMAL_DAILY_SESSIONS
    daily_sessions = int(base_sessions * multiplier)
    if anomaly == "holiday":
        daily_sessions = int(30_000 * multiplier)

    total_weight = sum(HOURLY_WEIGHTS)
    sessions: list[SessionSummary] = []

    for hour in range(24):
        hw = HOURLY_WEIGHTS[hour] / total_weight
        hourly_sessions = max(1, int(daily_sessions * hw))

        is_peak = 17 <= hour <= 20
        is_derby = multiplier >= 2.5
        is_outage = (anomaly == "cdn_outage" and
                     is_anomaly_active(
                         datetime(target_date.year, target_date.month, target_date.day,
                                  hour, 30) + timedelta(hours=3),
                         "cdn_outage"))

        for _ in range(hourly_sessions):
            sub = subscriber_pool[rng.randint(0, len(subscriber_pool) - 1)]

            session_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))
            content_type = rng.choices(["live", "vod"], weights=[0.7, 0.3], k=1)[0]
            channel = rng.choice(CHANNELS) if content_type == "live" else None
            content_id = f"cnt_{rng.randint(1000, 9999)}"
            cdn_provider = rng.choices(["medianova", "akamai"], weights=[0.85, 0.15], k=1)[0]

            # Startup time
            if is_derby and is_peak:
                startup_ms = rng.randint(2500, 12000)
            elif is_outage:
                startup_ms = rng.randint(4000, 15000)
            else:
                startup_ms = rng.randint(800, 1500)

            # Session duration
            if content_type == "live":
                total_ms = rng.randint(90 * 60_000, 120 * 60_000)  # 90-120 min
            else:
                total_ms = rng.randint(15 * 60_000, 90 * 60_000)  # 15-90 min

            # Buffer ratio
            if is_outage:
                buf_ratio = round(rng.uniform(0.10, 0.30), 4)
            elif is_derby and is_peak:
                buf_ratio = round(rng.uniform(0.02, 0.08), 4)
            else:
                buf_ratio = round(rng.uniform(0.001, 0.005), 4)

            total_buf_ms = int(total_ms * buf_ratio)
            watched_ms = total_ms - total_buf_ms

            # Bitrate
            if is_derby and is_peak:
                avg_br = rng.choice([1500, 900, 3000])
            else:
                avg_br = rng.choice([6000, 4500, 3000])

            # Events counts
            num_br_changes = rng.randint(0, 3)
            if is_derby:
                num_br_changes = rng.randint(2, 8)

            error_prob = 0.05
            if is_derby and is_peak:
                error_prob = 0.20
            if is_outage:
                error_prob = 0.40
            num_errors = 1 if rng.random() < error_prob else 0

            num_seeks = rng.randint(0, 3) if content_type == "vod" and rng.random() < 0.30 else 0

            completion = round(watched_ms / total_ms, 3) if total_ms > 0 else 0.0

            # Exit reason
            if num_errors > 0 and rng.random() < 0.3:
                exit_reason = "error"
            elif is_outage and rng.random() < 0.4:
                exit_reason = "network"
            else:
                exit_reason = rng.choices(
                    ["user", "app_close"], weights=[0.8, 0.2], k=1,
                )[0]

            qoe = compute_qoe_score(buf_ratio, startup_ms, num_errors, avg_br)
            player_ver = PLAYER_VERSIONS.get(sub.device_type, "HLS.js/1.4.12")

            sec = rng.randint(0, 3599)
            ts = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, sec // 60, sec % 60, tzinfo=timezone.utc,
            )

            sessions.append(SessionSummary(
                session_id=session_id,
                user_id_hash=hashlib.sha256(sub.user_id.encode()).hexdigest()[:32],
                device_type=sub.device_type,
                subscription_tier=sub.tier,
                content_id=content_id,
                content_type=content_type,
                channel=channel,
                country_code=sub.country if sub.country != "OTHER" else "GB",
                cdn_provider=cdn_provider,
                startup_time_ms=startup_ms,
                total_duration_ms=total_ms,
                watched_duration_ms=watched_ms,
                total_buffering_ms=total_buf_ms,
                buffer_ratio=buf_ratio,
                avg_bitrate_kbps=avg_br,
                num_bitrate_changes=num_br_changes,
                num_errors=num_errors,
                num_seeks=num_seeks,
                completion_rate=completion,
                exit_reason=exit_reason,
                final_qoe_score=qoe,
                session_start_ts=ts,
                player_version=player_ver,
            ))

    return sessions


class PlayerEventsGenerator(BaseGenerator):
    """Generates player event chains from session summaries."""

    @property
    def source_name(self) -> str:
        return "player_events"

    def _session_to_events(self, s: SessionSummary) -> list[dict]:
        """Convert a SessionSummary into a list of player event dicts."""
        base = {
            "session_id": s.session_id,
            "user_id_hash": s.user_id_hash,
            "device_type": s.device_type,
            "subscription_tier": s.subscription_tier,
            "content_id": s.content_id,
            "content_type": s.content_type,
            "channel": s.channel,
        }

        events: list[dict] = []
        ts = s.session_start_ts
        stream_hash = hashlib.sha256(f"stream_{s.content_id}_{s.channel}".encode()).hexdigest()[:32]

        # 1. session_start
        events.append({
            **base,
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "session_start",
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "initial_bitrate_kbps": s.avg_bitrate_kbps,
            "startup_time_ms": s.startup_time_ms,
            "player_version": s.player_version,
            "cdn_provider": s.cdn_provider,
            "stream_url_hash": stream_hash,
            "position_ms": None, "buffer_duration_ms": None, "buffer_ratio": None,
            "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
            "error_code": None, "error_fatal": None,
            "seek_from_ms": None, "seek_to_ms": None,
            "total_duration_ms": None, "watched_duration_ms": None,
            "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
        })

        cursor_ms = 0

        # 2. buffer events
        num_buffers = max(1, int(s.total_buffering_ms / max(1, self.rng.randint(500, 3000))))
        num_buffers = min(num_buffers, 10)
        for i in range(num_buffers):
            buf_start_offset = self.rng.randint(1, max(1, s.total_duration_ms // 1000))
            buf_ts = ts + timedelta(seconds=buf_start_offset)
            pos_ms = self.rng.randint(0, max(1, s.watched_duration_ms))
            buf_dur = max(100, s.total_buffering_ms // num_buffers)

            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "buffer_start",
                "timestamp": buf_ts.replace(tzinfo=None).isoformat() + "Z",
                "initial_bitrate_kbps": None, "startup_time_ms": None,
                "player_version": None, "cdn_provider": None, "stream_url_hash": None,
                "position_ms": pos_ms, "buffer_duration_ms": None, "buffer_ratio": None,
                "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
                "error_code": None, "error_fatal": None,
                "seek_from_ms": None, "seek_to_ms": None,
                "total_duration_ms": None, "watched_duration_ms": None,
                "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
            })

            buf_end_ts = buf_ts + timedelta(milliseconds=buf_dur)
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "buffer_end",
                "timestamp": buf_end_ts.replace(tzinfo=None).isoformat() + "Z",
                "initial_bitrate_kbps": None, "startup_time_ms": None,
                "player_version": None, "cdn_provider": None, "stream_url_hash": None,
                "position_ms": pos_ms,
                "buffer_duration_ms": buf_dur,
                "buffer_ratio": round(s.buffer_ratio, 4),
                "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
                "error_code": None, "error_fatal": None,
                "seek_from_ms": None, "seek_to_ms": None,
                "total_duration_ms": None, "watched_duration_ms": None,
                "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
            })

        # 3. bitrate_change events
        current_br = s.avg_bitrate_kbps
        for i in range(s.num_bitrate_changes):
            br_offset = self.rng.randint(1, max(1, s.total_duration_ms // 1000))
            br_ts = ts + timedelta(seconds=br_offset)
            new_br = self.rng.choice(BITRATE_PROFILES)
            reason = self.rng.choice(["bandwidth", "manual", "error", "startup"])

            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "bitrate_change",
                "timestamp": br_ts.replace(tzinfo=None).isoformat() + "Z",
                "initial_bitrate_kbps": None, "startup_time_ms": None,
                "player_version": None, "cdn_provider": None, "stream_url_hash": None,
                "position_ms": None, "buffer_duration_ms": None, "buffer_ratio": None,
                "from_bitrate_kbps": current_br,
                "to_bitrate_kbps": new_br,
                "change_reason": reason,
                "error_code": None, "error_fatal": None,
                "seek_from_ms": None, "seek_to_ms": None,
                "total_duration_ms": None, "watched_duration_ms": None,
                "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
            })
            current_br = new_br

        # 4. error events
        for i in range(s.num_errors):
            err_offset = self.rng.randint(1, max(1, s.total_duration_ms // 1000))
            err_ts = ts + timedelta(seconds=err_offset)
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "error",
                "timestamp": err_ts.replace(tzinfo=None).isoformat() + "Z",
                "initial_bitrate_kbps": None, "startup_time_ms": None,
                "player_version": None, "cdn_provider": None, "stream_url_hash": None,
                "position_ms": None, "buffer_duration_ms": None, "buffer_ratio": None,
                "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
                "error_code": self.rng.choice(ERROR_CODES),
                "error_fatal": self.rng.random() < 0.1,
                "seek_from_ms": None, "seek_to_ms": None,
                "total_duration_ms": None, "watched_duration_ms": None,
                "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
            })

        # 5. seek events (VOD only)
        for i in range(s.num_seeks):
            seek_offset = self.rng.randint(1, max(1, s.total_duration_ms // 1000))
            seek_ts = ts + timedelta(seconds=seek_offset)
            seek_from = self.rng.randint(0, max(1, s.watched_duration_ms))
            seek_to = self.rng.randint(0, max(1, s.watched_duration_ms))
            events.append({
                **base,
                "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
                "event_type": "seek",
                "timestamp": seek_ts.replace(tzinfo=None).isoformat() + "Z",
                "initial_bitrate_kbps": None, "startup_time_ms": None,
                "player_version": None, "cdn_provider": None, "stream_url_hash": None,
                "position_ms": None, "buffer_duration_ms": None, "buffer_ratio": None,
                "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
                "error_code": None, "error_fatal": None,
                "seek_from_ms": seek_from, "seek_to_ms": seek_to,
                "total_duration_ms": None, "watched_duration_ms": None,
                "completion_rate": None, "exit_reason": None, "final_qoe_score": None,
            })

        # 6. session_end
        end_ts = ts + timedelta(milliseconds=s.total_duration_ms)
        events.append({
            **base,
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "event_type": "session_end",
            "timestamp": end_ts.replace(tzinfo=None).isoformat() + "Z",
            "initial_bitrate_kbps": None, "startup_time_ms": None,
            "player_version": None, "cdn_provider": None, "stream_url_hash": None,
            "position_ms": None, "buffer_duration_ms": None, "buffer_ratio": None,
            "from_bitrate_kbps": None, "to_bitrate_kbps": None, "change_reason": None,
            "error_code": None, "error_fatal": None,
            "seek_from_ms": None, "seek_to_ms": None,
            "total_duration_ms": s.total_duration_ms,
            "watched_duration_ms": s.watched_duration_ms,
            "completion_rate": s.completion_rate,
            "exit_reason": s.exit_reason,
            "final_qoe_score": s.final_qoe_score,
        })

        return events

    def generate_day(self, target_date: date) -> int:
        """Generate all player events for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)

        sessions = generate_sessions_for_day(
            self.rng, target_date, self.subscriber_pool, multiplier, anomaly,
        )

        all_events: list[dict] = []
        for s in sessions:
            all_events.extend(self._session_to_events(s))

        # Sort by timestamp
        all_events.sort(key=lambda r: r["timestamp"])

        # Write to 5-minute files
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
            "player_events_day_complete",
            date=target_date.isoformat(),
            records=total,
            sessions=len(sessions),
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    PlayerEventsGenerator().generate_all()
