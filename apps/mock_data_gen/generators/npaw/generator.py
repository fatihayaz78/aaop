"""NPAW Analytics generator — post-session aggregates correlated with Player Events.

Output: npaw/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz (one file per day)
Uses same seed as PlayerEventsGenerator for deterministic correlation.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import get_anomaly_for_date
from apps.mock_data_gen.generators.player_events.generator import (
    generate_sessions_for_day,
    SessionSummary,
)

logger = structlog.get_logger(__name__)


class NPAWGenerator(BaseGenerator):
    """Generates NPAW post-session analytics from Player Events session data."""

    @property
    def source_name(self) -> str:
        return "npaw"

    def _session_to_npaw(self, s: SessionSummary) -> dict:
        """Convert a PlayerEvents SessionSummary to an NPAW aggregate record."""
        # Rebuffering ratio with small noise (±5% relative)
        rebuf_ratio = s.buffer_ratio
        noise = self.rng.uniform(-0.05, 0.05) * rebuf_ratio
        rebuf_ratio = round(max(0.0, rebuf_ratio + noise), 5)

        # QoE score with ±0.1 noise
        qoe_noise = self.rng.uniform(-0.1, 0.1)
        qoe_score = round(max(0.0, min(5.0, s.final_qoe_score + qoe_noise)), 2)

        # Youbora score = qoe × 2.0 (0-10 scale)
        youbora_score = round(min(10.0, qoe_score * 2.0), 2)

        # Exit before video start
        exit_before = s.startup_time_ms > 8000 or s.total_duration_ms < 5000

        # Unique renditions = 1 + num_bitrate_changes (capped)
        unique_renditions = min(6, 1 + s.num_bitrate_changes)

        # Timestamp = session end
        end_ts = s.session_start_ts + timedelta(milliseconds=s.total_duration_ms)

        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "session_id": s.session_id,
            "timestamp": end_ts.replace(tzinfo=None).isoformat() + "Z",
            "user_id_hash": s.user_id_hash,
            "device_type": s.device_type,
            "subscription_tier": s.subscription_tier,
            "content_id": s.content_id,
            "content_type": s.content_type,
            "channel": s.channel,
            "cdn_provider": s.cdn_provider,
            "country_code": s.country_code,
            "startup_time_ms": s.startup_time_ms,
            "total_buffering_ms": s.total_buffering_ms,
            "rebuffering_ratio": rebuf_ratio,
            "avg_bitrate_kbps": s.avg_bitrate_kbps,
            "num_bitrate_changes": s.num_bitrate_changes,
            "num_errors": s.num_errors,
            "num_seeks": s.num_seeks,
            "session_duration_ms": s.total_duration_ms,
            "watched_duration_ms": s.watched_duration_ms,
            "completion_rate": s.completion_rate,
            "exit_before_video_start": exit_before,
            "unique_renditions_played": unique_renditions,
            "youbora_score": youbora_score,
            "qoe_score": qoe_score,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate NPAW aggregates for a single day."""
        multiplier = self.get_multiplier(target_date)
        anomaly = get_anomaly_for_date(target_date)

        # Use a separate RNG for session generation (same seed → same sessions)
        import random
        session_rng = random.Random(self.seed + target_date.toordinal())

        sessions = generate_sessions_for_day(
            session_rng, target_date, self.subscriber_pool, multiplier, anomaly,
        )

        records = [self._session_to_npaw(s) for s in sessions]

        # Write single daily file
        self.write_jsonl_gz(
            records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.jsonl.gz",
        )

        total = len(records)
        logger.info(
            "npaw_day_complete",
            date=target_date.isoformat(),
            records=total,
            multiplier=multiplier,
        )
        return total


if __name__ == "__main__":
    NPAWGenerator().generate_all()
