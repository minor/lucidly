"""Lightweight server-side scoring sessions for tamper-proof leaderboard submissions.

Write-behind cache: the in-memory dict is the fast primary store. Every mutation
fires a background asyncio task that upserts to Supabase. On cache miss (e.g. after
a server restart), the session is lazily recovered from the DB.
"""

import asyncio
import logging
import time
import uuid
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 3600  # 1 hour


class ScoringSession(BaseModel):
    id: str
    challenge_id: str
    username: str
    model: str = "unknown"
    started_at: float
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_turns: int = 0
    total_cost: float = 0.0
    server_processing_seconds: float = 0.0
    messages: list[dict] = []
    status: str = "active"  # active | completed
    frozen_at: float | None = None  # when set, submission uses this instead of time.time()
    last_test_accuracy: float | None = None  # cached from the most recent run-tests call


_scoring_sessions: dict[str, ScoringSession] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_expired(session: ScoringSession) -> bool:
    return time.time() - session.started_at > SESSION_TTL_SECONDS


def _to_db_dict(session: ScoringSession) -> dict:
    """Serialise a ScoringSession to the flat dict expected by Supabase."""
    return session.model_dump()


def _persist_async(session_id: str) -> None:
    """Fire-and-forget: schedule a background DB upsert for *session_id*.

    If no running event loop exists (e.g. in synchronous unit tests), the call
    is silently skipped so the existing test suite stays green.
    """
    session = _scoring_sessions.get(session_id)
    if session is None:
        return
    snapshot = _to_db_dict(session)

    async def _do_upsert() -> None:
        try:
            from database import save_scoring_session
            await save_scoring_session(snapshot)
        except Exception:
            logger.debug("Background DB upsert failed for session %s", session_id[:8], exc_info=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_do_upsert())
    except RuntimeError:
        # No running event loop — we're in a sync context (tests). Skip silently.
        pass


def _delete_async(session_id: str) -> None:
    """Fire-and-forget: schedule a background DB delete for *session_id*."""
    async def _do_delete() -> None:
        try:
            from database import delete_scoring_session_db
            await delete_scoring_session_db(session_id)
        except Exception:
            logger.debug("Background DB delete failed for session %s", session_id[:8], exc_info=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_do_delete())
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_scoring_session(
    challenge_id: str, username: str, model: str = "unknown"
) -> ScoringSession:
    session = ScoringSession(
        id=str(uuid.uuid4()),
        challenge_id=challenge_id,
        username=username,
        model=model,
        started_at=time.time(),
    )
    _scoring_sessions[session.id] = session
    _persist_async(session.id)
    return session


def get_scoring_session(session_id: str) -> ScoringSession | None:
    # ── 1. Fast path: already in memory ──────────────────────────────────────
    session = _scoring_sessions.get(session_id)
    if session is not None:
        if _is_expired(session):
            del _scoring_sessions[session_id]
            # DB cleanup is handled by pg_cron; no explicit delete needed here.
            return None
        return session

    # ── 2. Cache miss: try to recover from Supabase (e.g. after restart) ─────
    async def _load() -> ScoringSession | None:
        from database import load_scoring_session
        row = await load_scoring_session(session_id)
        if row is None:
            return None
        try:
            recovered = ScoringSession(**row)
        except Exception as e:
            logger.warning("Could not deserialise session %s from DB: %s", session_id[:8], e)
            return None
        if _is_expired(recovered):
            return None
        _scoring_sessions[recovered.id] = recovered
        logger.info("Rehydrated scoring session %s from Supabase", session_id[:8])
        return recovered

    # Run the async load synchronously if we have a running loop, otherwise
    # use asyncio.run() — but that would block, so instead we attempt a
    # best-effort approach using the running loop's run_until_complete via
    # a future. In practice this function is always called from an async
    # request handler, so get_running_loop() will succeed.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Sync context (tests) — no DB fallback available.
        return None

    # We cannot await inside a non-async function, so we schedule and block
    # via run_until_complete on a *new* loop would deadlock. Instead we use
    # asyncio.ensure_future and rely on the fact that FastAPI dependency
    # resolution calls us inside a coroutine chain — we need to be awaitable.
    # The cleanest solution: make the sync wrapper return None and let the
    # async cousin below handle the real work.
    #
    # Actually the correct pattern here is to make get_scoring_session async.
    # But that would require changing all call-sites. Instead we expose a
    # companion async function  `aget_scoring_session` for the endpoints that
    # can await, and keep the sync version as a fast-path-only helper used
    # inside the cleanup loop.
    return None  # caller should use aget_scoring_session


async def aget_scoring_session(session_id: str) -> ScoringSession | None:
    """Async version of get_scoring_session — falls back to DB on cache miss.

    Use this in all async FastAPI endpoint handlers. The sync ``get_scoring_session``
    is kept for the cleanup loop (which only operates on already-cached sessions).
    """
    # ── 1. Fast path ─────────────────────────────────────────────────────────
    session = _scoring_sessions.get(session_id)
    if session is not None:
        if _is_expired(session):
            del _scoring_sessions[session_id]
            return None
        return session

    # ── 2. DB fallback ───────────────────────────────────────────────────────
    try:
        from database import load_scoring_session
        row = await load_scoring_session(session_id)
    except Exception as e:
        logger.warning("DB load failed for session %s: %s", session_id[:8], e)
        return None

    if row is None:
        return None

    try:
        recovered = ScoringSession(**row)
    except Exception as e:
        logger.warning("Could not deserialise session %s from DB: %s", session_id[:8], e)
        return None

    if _is_expired(recovered):
        return None

    _scoring_sessions[recovered.id] = recovered
    logger.info("Rehydrated scoring session %s from Supabase after restart", session_id[:8])
    return recovered


def record_turn(
    session_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    user_message: str,
    assistant_message: str,
) -> None:
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    session.total_turns += 1
    session.total_input_tokens += input_tokens
    session.total_output_tokens += output_tokens
    session.total_cost += cost
    session.messages.append({"role": "user", "content": user_message})
    session.messages.append({"role": "assistant", "content": assistant_message})
    _persist_async(session_id)


def record_processing_time(session_id: str, seconds: float) -> None:
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    session.server_processing_seconds += seconds
    _persist_async(session_id)


def freeze_timer(session_id: str) -> None:
    """Freeze the session timer (e.g. when 100% accuracy is achieved)."""
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    if session.frozen_at is None:
        session.frozen_at = time.time()
        _persist_async(session_id)


def unfreeze_timer(session_id: str) -> None:
    """Unfreeze the session timer (e.g. if accuracy drops below 100%)."""
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    session.frozen_at = None
    _persist_async(session_id)


def record_partial_turn(
    session_id: str,
    *,
    partial_response: str,
    user_message: str,
    model: str = "unknown",
) -> None:
    """Record a turn that was aborted mid-stream, estimating tokens from text length."""
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    from config import MODEL_PRICING, _DEFAULT_PRICING
    est_input = len(user_message.split()) * 2
    est_output = len(partial_response.split()) * 2
    pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    cost = (est_input * pricing["input"] + est_output * pricing["output"]) / 1_000_000
    session.total_turns += 1
    session.total_input_tokens += est_input
    session.total_output_tokens += est_output
    session.total_cost += cost
    session.messages.append({"role": "user", "content": user_message})
    session.messages.append({"role": "assistant", "content": partial_response})
    _persist_async(session_id)


def complete_scoring_session(session_id: str) -> ScoringSession | None:
    session = _scoring_sessions.get(session_id)
    if session is None:
        return None
    session.status = "completed"
    _persist_async(session_id)
    return session


def delete_scoring_session(session_id: str) -> None:
    _scoring_sessions.pop(session_id, None)
    _delete_async(session_id)


def cleanup_expired_sessions() -> int:
    """Remove sessions older than SESSION_TTL_SECONDS from memory.

    Returns count of removed sessions.
    DB cleanup is handled automatically by pg_cron — no explicit deletes needed.
    """
    now = time.time()
    expired_ids = [
        sid
        for sid, session in _scoring_sessions.items()
        if now - session.started_at > SESSION_TTL_SECONDS
    ]
    for sid in expired_ids:
        del _scoring_sessions[sid]
    if expired_ids:
        logger.info("Cleaned up %d expired scoring session(s) from memory", len(expired_ids))
    return len(expired_ids)
