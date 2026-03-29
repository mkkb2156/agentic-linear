"""Dashboard WebSocket — real-time agent events via Redis pub/sub."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# Active WebSocket connections
_connections: set[WebSocket] = set()


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time dashboard updates.

    Subscribes to Redis pub/sub and forwards agent events to the client.
    Also sends periodic heartbeats and initial state on connect.
    """
    await websocket.accept()
    _connections.add(websocket)
    logger.info("WebSocket client connected (total: %d)", len(_connections))

    redis_queue = getattr(websocket.app.state, "redis_queue", None)
    pubsub = None

    try:
        # Send initial agent states
        state_tracker = getattr(websocket.app.state, "state_tracker", None)
        if state_tracker:
            states = await state_tracker.get_all()
            await websocket.send_json({"type": "initial_state", "data": states})

        # Subscribe to Redis events if available
        if redis_queue:
            pubsub = await redis_queue.subscribe_events()
            await _relay_events(websocket, pubsub)
        else:
            # No Redis — just keep connection alive with heartbeats
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        _connections.discard(websocket)
        if pubsub:
            await pubsub.unsubscribe()
            await pubsub.close()
        logger.info("WebSocket client disconnected (total: %d)", len(_connections))


async def _relay_events(websocket: WebSocket, pubsub: Any) -> None:
    """Relay Redis pub/sub messages to WebSocket client."""
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
        if message and message["type"] == "message":
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            try:
                event = json.loads(data)
                await websocket.send_json(event)
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # Send heartbeat on timeout
            await websocket.send_json({"type": "heartbeat"})


async def broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _connections.difference_update(disconnected)
