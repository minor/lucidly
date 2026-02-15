"""
In-process session event broadcast for agent runs.
Allows backend (e.g. agent_runner) to push token progress and session updates
to the frontend via SSE without circular imports.
"""

import asyncio
from typing import Any

# session_id -> list of queues (one per connected SSE client)
_session_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}


def _queues_for(session_id: str) -> list[asyncio.Queue[dict[str, Any]]]:
    if session_id not in _session_queues:
        _session_queues[session_id] = []
    return _session_queues[session_id]


def subscribe_session_events(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Create a queue for this client; caller must remove it on disconnect."""
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _queues_for(session_id).append(q)
    return q


def unsubscribe_session_events(session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Remove the queue when client disconnects."""
    if session_id in _session_queues:
        try:
            _session_queues[session_id].remove(queue)
        except ValueError:
            pass


async def broadcast_session_event(session_id: str, event: dict[str, Any]) -> None:
    """Push an event to all clients subscribed to this session (e.g. agent run page)."""
    for q in _queues_for(session_id)[:]:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
