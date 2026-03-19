"""Socket.IO broadcast manager for real-time updates."""

from __future__ import annotations

import socketio
import structlog

logger = structlog.get_logger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=["http://localhost:3000"])


@sio.event
async def connect(sid: str, environ: dict) -> None:
    logger.info("ws_connected", sid=sid)


@sio.event
async def disconnect(sid: str) -> None:
    logger.info("ws_disconnected", sid=sid)


async def broadcast(event: str, data: dict) -> None:
    await sio.emit(event, data)
    logger.info("ws_broadcast", event_name=event)
