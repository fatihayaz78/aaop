"""Tests for backend/websocket/manager.py — WebSocketManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.websocket.manager import WebSocketManager


@pytest.mark.asyncio
async def test_broadcast():
    """Broadcasting sends JSON to connected websockets."""
    mgr = WebSocketManager()

    # Mock websocket
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()

    await mgr.connect(mock_ws, "ops_center", "t1")
    await mgr.broadcast("ops_center", "t1", {"event": "test", "data": "value"})

    mock_ws.send_json.assert_called_once_with({"event": "test", "data": "value"})


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    """Disconnecting removes the websocket from the manager."""
    mgr = WebSocketManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    await mgr.connect(mock_ws, "ops_center", "t1")
    assert mgr.connection_count == 1

    mgr.disconnect(mock_ws, "ops_center", "t1")
    assert mgr.connection_count == 0
