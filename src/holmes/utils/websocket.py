import asyncio
import logging
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

from holmes.api.utils import convert_for_json

logger = logging.getLogger("holmes")


async def safe_send(ws: WebSocket, event: str, data: Any) -> bool:
    """
    Safely send a message through WebSocket with error handling.

    Parameters
    ----------
    ws : WebSocket
        The WebSocket connection
    event : str
        Event type for the message
    data : Any
        Data to send (will be converted to JSON-safe format)

    Returns
    -------
    bool
        True if message was sent successfully, False otherwise
    """
    if ws.client_state != WebSocketState.CONNECTED:
        logger.debug(f"Cannot send '{event}': WebSocket not connected")
        return False

    try:
        await ws.send_json({"type": event, "data": convert_for_json(data)})
        return True
    except RuntimeError as exc:
        # Connection closed during send
        logger.debug(f"Failed to send '{event}': {exc}")
        return False
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Unexpected error sending '{event}': {exc}")
        return False


# Alias for convenience
send = safe_send


def create_monitored_task(
    coro: Any,
    ws: WebSocket,
    task_name: str = "background_task",
) -> asyncio.Task:

    async def monitored_wrapper() -> None:
        try:
            await coro
        except asyncio.CancelledError:
            logger.debug(f"Task '{task_name}' was cancelled")
            raise
        except Exception as exc:
            logger.exception(f"Task '{task_name}' failed: {exc}")
            await safe_send(ws, "error", f"Operation failed: {str(exc)}")

    task = asyncio.create_task(monitored_wrapper(), name=task_name)

    # Track task in WebSocket state for cleanup
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(lambda t: ws.state.tasks.discard(t))

    return task


async def cleanup_websocket(ws: WebSocket) -> None:
    # cancel any pending tasks
    if hasattr(ws.state, "tasks"):
        for task in list(ws.state.tasks):
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        ws.state.tasks.clear()

    if hasattr(ws.state, "stop_event"):
        delattr(ws.state, "stop_event")

    logger.debug("WebSocket cleanup completed")
