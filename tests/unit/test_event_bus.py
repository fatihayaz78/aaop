"""Tests for shared/event_bus.py."""

from __future__ import annotations

import asyncio

import pytest

from shared.event_bus import EVENT_ROUTING, EventBus, EventType, get_event_bus
from shared.schemas.base_event import BaseEvent


def test_event_type_count():
    assert len(EventType) == 9


def test_event_routing_keys():
    for et in EventType:
        assert et in EVENT_ROUTING
        assert "pub" in EVENT_ROUTING[et]
        assert "subs" in EVENT_ROUTING[et]


@pytest.mark.asyncio
async def test_publish_subscribe(event_bus: EventBus):
    received: list[BaseEvent] = []

    async def handler(event: BaseEvent) -> None:
        received.append(event)

    event_bus.subscribe(EventType.CDN_ANOMALY_DETECTED, handler)
    await event_bus.start()

    event = BaseEvent(
        event_type=EventType.CDN_ANOMALY_DETECTED,
        tenant_id="t1",
        source_app="log_analyzer",
    )
    await event_bus.publish(event)
    await asyncio.sleep(0.1)  # give processor time

    assert len(received) == 1
    assert received[0].event_id == event.event_id

    await event_bus.stop()


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus: EventBus):
    results: list[str] = []

    async def handler_a(event: BaseEvent) -> None:
        results.append("a")

    async def handler_b(event: BaseEvent) -> None:
        results.append("b")

    event_bus.subscribe(EventType.INCIDENT_CREATED, handler_a)
    event_bus.subscribe(EventType.INCIDENT_CREATED, handler_b)
    await event_bus.start()

    event = BaseEvent(
        event_type=EventType.INCIDENT_CREATED,
        tenant_id="t1",
        source_app="ops_center",
    )
    await event_bus.publish(event)
    await asyncio.sleep(0.1)

    assert sorted(results) == ["a", "b"]
    await event_bus.stop()


@pytest.mark.asyncio
async def test_unsubscribed_event_ignored(event_bus: EventBus):
    received: list[BaseEvent] = []

    async def handler(event: BaseEvent) -> None:
        received.append(event)

    event_bus.subscribe(EventType.CDN_ANOMALY_DETECTED, handler)
    await event_bus.start()

    event = BaseEvent(
        event_type=EventType.INCIDENT_CREATED,  # different type
        tenant_id="t1",
        source_app="ops_center",
    )
    await event_bus.publish(event)
    await asyncio.sleep(0.1)

    assert len(received) == 0
    await event_bus.stop()


@pytest.mark.asyncio
async def test_handler_error_does_not_crash(event_bus: EventBus):
    """Handler that raises should not crash the event bus."""
    call_count = 0

    async def failing_handler(event: BaseEvent) -> None:
        msg = "handler error"
        raise RuntimeError(msg)

    async def counting_handler(event: BaseEvent) -> None:
        nonlocal call_count
        call_count += 1

    event_bus.subscribe(EventType.CDN_ANOMALY_DETECTED, failing_handler)
    event_bus.subscribe(EventType.CDN_ANOMALY_DETECTED, counting_handler)
    await event_bus.start()

    event = BaseEvent(event_type=EventType.CDN_ANOMALY_DETECTED, tenant_id="t1", source_app="test")
    await event_bus.publish(event)
    await asyncio.sleep(0.1)

    assert call_count == 1  # second handler still runs
    await event_bus.stop()


@pytest.mark.asyncio
async def test_unknown_event_type(event_bus: EventBus):
    """Events with unknown type should be logged but not crash."""
    await event_bus.start()
    event = BaseEvent(event_type="unknown_event", tenant_id="t1", source_app="test")
    await event_bus.publish(event)
    await asyncio.sleep(0.1)
    await event_bus.stop()


def test_get_event_bus_singleton():
    import shared.event_bus as eb

    old = eb._event_bus
    eb._event_bus = None
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2
    eb._event_bus = old


@pytest.mark.asyncio
async def test_stop_without_start(event_bus: EventBus):
    """Stop without start should not raise."""
    await event_bus.stop()
