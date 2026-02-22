"""Lightweight server-side scoring sessions for tamper-proof leaderboard submissions."""

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
    return session


def get_scoring_session(session_id: str) -> ScoringSession | None:
    return _scoring_sessions.get(session_id)


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


def record_processing_time(session_id: str, seconds: float) -> None:
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    session.server_processing_seconds += seconds


def freeze_timer(session_id: str) -> None:
    """Freeze the session timer (e.g. when 100% accuracy is achieved)."""
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    if session.frozen_at is None:
        session.frozen_at = time.time()


def unfreeze_timer(session_id: str) -> None:
    """Unfreeze the session timer (e.g. if accuracy drops below 100%)."""
    session = _scoring_sessions.get(session_id)
    if session is None or session.status != "active":
        return
    session.frozen_at = None


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


def complete_scoring_session(session_id: str) -> ScoringSession | None:
    session = _scoring_sessions.get(session_id)
    if session is None:
        return None
    session.status = "completed"
    return session


def delete_scoring_session(session_id: str) -> None:
    _scoring_sessions.pop(session_id, None)


def cleanup_expired_sessions() -> int:
    """Remove sessions older than SESSION_TTL_SECONDS. Returns count of removed sessions."""
    now = time.time()
    expired_ids = [
        sid
        for sid, session in _scoring_sessions.items()
        if now - session.started_at > SESSION_TTL_SECONDS
    ]
    for sid in expired_ids:
        del _scoring_sessions[sid]
    if expired_ids:
        logger.info("Cleaned up %d expired scoring session(s)", len(expired_ids))
    return len(expired_ids)
