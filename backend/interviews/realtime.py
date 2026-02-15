"""WebSocket / SSE event broadcasting for interview observation."""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# room_id -> set of asyncio.Queue
_observers: dict[str, set[asyncio.Queue]] = {}


def subscribe(room_id: str) -> asyncio.Queue:
    """Register a new observer for a room. Returns a queue to await events from."""
    queue: asyncio.Queue = asyncio.Queue()
    _observers.setdefault(room_id, set()).add(queue)
    return queue


def unsubscribe(room_id: str, queue: asyncio.Queue) -> None:
    """Remove an observer."""
    if room_id in _observers:
        _observers[room_id].discard(queue)
        if not _observers[room_id]:
            del _observers[room_id]


async def broadcast(room_id: str, event: dict[str, Any]) -> None:
    """Push an event to all observers of a room."""
    queues = _observers.get(room_id, set())
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Observer queue full for room %s, dropping event", room_id)
