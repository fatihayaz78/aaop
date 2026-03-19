"""Tests for backend/websocket/manager.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.websocket.manager import broadcast, sio


@pytest.mark.asyncio
async def test_broadcast():
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await broadcast("test_event", {"data": "value"})
        mock_emit.assert_called_once_with("test_event", {"data": "value"})
