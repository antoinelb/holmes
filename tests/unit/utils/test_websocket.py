"""Unit tests for holmes.utils.websocket module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketState

from holmes.utils.websocket import (
    cleanup_websocket,
    create_monitored_task,
    safe_send,
    send,
)


class TestSafeSend:
    """Tests for safe_send function."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        """safe_send returns True on successful send."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        result = await safe_send(ws, "test", {"key": "value"})

        assert result is True
        ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_not_connected(self):
        """safe_send returns False when WebSocket is not connected."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.DISCONNECTED

        result = await safe_send(ws, "test", {"key": "value"})

        assert result is False

    @pytest.mark.asyncio
    async def test_send_runtime_error(self):
        """safe_send returns False on RuntimeError."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock(side_effect=RuntimeError("Connection closed"))

        result = await safe_send(ws, "test", {"key": "value"})

        assert result is False

    def test_send_alias(self):
        """send is an alias for safe_send."""
        assert send is safe_send


class TestCreateMonitoredTask:
    """Tests for create_monitored_task function."""

    @pytest.mark.asyncio
    async def test_task_completes_normally(self):
        """Monitored task completes normally."""

        async def coro():
            return "result"

        ws = MagicMock()
        ws.state = MagicMock()
        ws.state.tasks = set()

        task = create_monitored_task(coro(), ws)
        await task

        assert task.done()

    @pytest.mark.asyncio
    async def test_task_exception_sends_error(self):
        """Monitored task exception sends error to WebSocket."""

        async def failing_coro():
            raise ValueError("Test error")

        ws = MagicMock()
        ws.state = MagicMock()
        ws.state.tasks = set()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        task = create_monitored_task(failing_coro(), ws)

        # Wait for task to complete
        await asyncio.sleep(0.1)

        # Task should be done
        assert task.done()

        # Error should have been sent
        ws.send_json.assert_called()


class TestCleanupWebsocket:
    """Tests for cleanup_websocket function."""

    @pytest.mark.asyncio
    async def test_cleanup_with_no_tasks(self):
        """cleanup_websocket handles websocket with no tasks."""
        ws = MagicMock()
        ws.state = MagicMock(spec=[])  # No 'tasks' attribute

        # Should not raise
        await cleanup_websocket(ws)

    @pytest.mark.asyncio
    async def test_cleanup_cancels_pending_tasks(self):
        """cleanup_websocket cancels pending tasks."""
        ws = MagicMock()
        ws.state = MagicMock()

        # Create a task that won't complete on its own
        async def long_running():
            await asyncio.sleep(10)

        task = asyncio.create_task(long_running())
        ws.state.tasks = {task}

        await cleanup_websocket(ws)

        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_cleanup_clears_stop_event(self):
        """cleanup_websocket removes stop_event from state."""
        ws = MagicMock()
        ws.state = MagicMock()
        ws.state.tasks = set()
        ws.state.stop_event = asyncio.Event()

        await cleanup_websocket(ws)

        # stop_event should be deleted
        assert not hasattr(ws.state, "stop_event")
