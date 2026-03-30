"""Anomaly Engine — continuous polling loop for real-time detection.

Polls logs.duckdb every 30s via 4 detectors. Publishes to EventBus on anomaly.
Does NOT scan historical data on startup — only new data since last check.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any

import structlog

from shared.realtime.detectors.api_detector import APIDetector
from shared.realtime.detectors.base_detector import AnomalyEvent, BaseDetector
from shared.realtime.detectors.cdn_detector import CDNDetector
from shared.realtime.detectors.drm_detector import DRMDetector
from shared.realtime.detectors.qoe_detector import QoEDetector

logger = structlog.get_logger(__name__)


class AnomalyEngine:
    """Real-time anomaly detection engine — polls logs.duckdb every 30s."""

    def __init__(self, tenant_id: str = "aaop_company", schema: str = "aaop_company") -> None:
        self.tenant_id = tenant_id
        self.schema = schema
        self.detectors: list[BaseDetector] = [
            CDNDetector(),
            DRMDetector(),
            QoEDetector(),
            APIDetector(),
        ]
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._recent_anomalies: list[AnomalyEvent] = []
        self._last_cycle_at: datetime | None = None
        self._anomalies_24h: int = 0

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("anomaly_engine_started", tenant_id=self.tenant_id,
                     detectors=[d.name for d in self.detectors])

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("anomaly_engine_stopped")

    async def _poll_loop(self) -> None:
        # Skip first cycle on startup to avoid scanning old data as "new"
        await asyncio.sleep(30)

        while self._running:
            try:
                await self._run_cycle()
            except Exception as exc:
                logger.error("anomaly_engine_cycle_error", error=str(exc))

            await asyncio.sleep(30)

    async def _run_cycle(self) -> None:
        all_anomalies: list[AnomalyEvent] = []

        for detector in self.detectors:
            if not detector.enabled:
                continue
            try:
                events = await detector.check(self.tenant_id, self.schema)
                all_anomalies.extend(events)
            except Exception as exc:
                logger.warning("detector_error", detector=detector.name, error=str(exc))

        self._last_cycle_at = datetime.now(timezone.utc)

        if all_anomalies:
            self._anomalies_24h += len(all_anomalies)
            self._recent_anomalies = (all_anomalies + self._recent_anomalies)[:200]

            for event in all_anomalies:
                logger.warning("anomaly_detected",
                               detector=event.detector, metric=event.metric,
                               severity=event.severity, value=event.current_value,
                               threshold=event.threshold)

            # Publish to EventBus
            await self._publish_anomalies(all_anomalies)

    async def _publish_anomalies(self, events: list[AnomalyEvent]) -> None:
        try:
            from shared.event_bus import EventType, get_event_bus
            from shared.schemas.base_event import BaseEvent, SeverityLevel

            bus = get_event_bus()
            for event in events:
                severity = SeverityLevel(event.severity) if event.severity in ("P0", "P1", "P2", "P3") else SeverityLevel.P2

                if event.detector in ("cdn_detector",):
                    event_type = EventType.CDN_ANOMALY_DETECTED
                elif event.detector in ("qoe_detector",):
                    event_type = EventType.QOE_DEGRADATION
                else:
                    event_type = EventType.CDN_ANOMALY_DETECTED  # fallback

                await bus.publish(BaseEvent(
                    event_type=event_type,
                    tenant_id=event.tenant_id,
                    source_app="realtime_engine",
                    severity=severity,
                    payload={
                        "detector": event.detector,
                        "metric": event.metric,
                        "current_value": event.current_value,
                        "threshold": event.threshold,
                    },
                ))
        except Exception as exc:
            logger.debug("anomaly_publish_failed", error=str(exc))

    def get_recent(self, minutes: int = 60) -> list[AnomalyEvent]:
        cutoff = datetime.now(timezone.utc).timestamp() - (minutes * 60)
        return [a for a in self._recent_anomalies if a.detected_at.timestamp() > cutoff]

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "detectors": [
                {"name": d.name, "enabled": d.enabled, "interval_s": d.poll_interval_seconds}
                for d in self.detectors
            ],
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "anomalies_24h": self._anomalies_24h,
            "recent_count": len(self._recent_anomalies),
        }

    def toggle_detector(self, name: str, enabled: bool) -> bool:
        for d in self.detectors:
            if d.name == name:
                d.enabled = enabled
                logger.info("detector_toggled", name=name, enabled=enabled)
                return True
        return False


# Singleton
_engine: AnomalyEngine | None = None


def get_anomaly_engine() -> AnomalyEngine:
    global _engine
    if _engine is None:
        _engine = AnomalyEngine()
    return _engine
