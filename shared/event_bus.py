"""Cross-app Event Bus using asyncio.Queue. GCP migration: swap to Pub/Sub adaptor."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any

import structlog

from shared.schemas.base_event import BaseEvent

logger = structlog.get_logger(__name__)


class EventType(StrEnum):
    CDN_ANOMALY_DETECTED = "cdn_anomaly_detected"
    INCIDENT_CREATED = "incident_created"
    RCA_COMPLETED = "rca_completed"
    QOE_DEGRADATION = "qoe_degradation"
    LIVE_EVENT_STARTING = "live_event_starting"
    EXTERNAL_DATA_UPDATED = "external_data_updated"
    CHURN_RISK_DETECTED = "churn_risk_detected"
    SCALE_RECOMMENDATION = "scale_recommendation"
    ANALYSIS_COMPLETE = "analysis_complete"


EVENT_ROUTING: dict[EventType, dict[str, Any]] = {
    EventType.CDN_ANOMALY_DETECTED: {"pub": "log_analyzer", "subs": ["ops_center", "alert_center"]},
    EventType.INCIDENT_CREATED: {"pub": "ops_center", "subs": ["alert_center", "knowledge_base"]},
    EventType.RCA_COMPLETED: {"pub": "ops_center", "subs": ["knowledge_base", "alert_center"]},
    EventType.QOE_DEGRADATION: {"pub": "viewer_experience", "subs": ["ops_center", "alert_center"]},
    EventType.LIVE_EVENT_STARTING: {"pub": "live_intelligence", "subs": ["ops_center", "log_analyzer", "alert_center"]},
    EventType.EXTERNAL_DATA_UPDATED: {"pub": "live_intelligence", "subs": ["ops_center", "growth_retention"]},
    EventType.CHURN_RISK_DETECTED: {"pub": "growth_retention", "subs": ["alert_center"]},
    EventType.SCALE_RECOMMENDATION: {"pub": "capacity_cost", "subs": ["ops_center", "alert_center"]},
    EventType.ANALYSIS_COMPLETE: {"pub": "log_analyzer", "subs": ["growth_retention", "viewer_experience"]},
}

EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """In-process event bus backed by asyncio.Queue per subscriber."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)
        logger.info("event_bus_subscribed", event_type=event_type.value)

    async def publish(self, event: BaseEvent) -> None:
        await self._queue.put(event)
        logger.info(
            "event_bus_published",
            event_type=event.event_type,
            event_id=event.event_id,
            tenant_id=event.tenant_id,
        )

    async def _process(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                event_type = EventType(event.event_type)
            except ValueError:
                logger.warning("event_bus_unknown_type", event_type=event.event_type)
                continue
            handlers = self._subscribers.get(event_type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception("event_bus_handler_error", event_type=event_type.value)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._process())
        logger.info("event_bus_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("event_bus_stopped")


# Singleton
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
