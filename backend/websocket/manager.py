"""WebSocket manager — native FastAPI WebSocket with per-tenant, per-app routing."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, list[WebSocket]]] = defaultdict(
            lambda: defaultdict(list)
        )

    async def connect(self, websocket: WebSocket, app: str, tenant_id: str) -> None:
        await websocket.accept()
        self._connections[tenant_id][app].append(websocket)
        logger.info("ws_connected", app=app, tenant_id=tenant_id)

    def disconnect(self, websocket: WebSocket, app: str, tenant_id: str) -> None:
        conns = self._connections[tenant_id][app]
        if websocket in conns:
            conns.remove(websocket)
        logger.info("ws_disconnected", app=app, tenant_id=tenant_id)

    async def broadcast(self, app: str, tenant_id: str, message: dict[str, Any]) -> None:
        conns = self._connections[tenant_id][app]
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.remove(ws)

    async def broadcast_all_tenants(self, app: str, message: dict[str, Any]) -> None:
        for tenant_id in self._connections:
            await self.broadcast(app, tenant_id, message)

    @property
    def connection_count(self) -> int:
        total = 0
        for tenant in self._connections.values():
            for conns in tenant.values():
                total += len(conns)
        return total


ws_manager = WebSocketManager()
