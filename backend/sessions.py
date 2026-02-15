"""In-memory session management for Lucidly MVP."""

import time
import uuid
from typing import Any

from pydantic import BaseModel


class Turn(BaseModel):
    turn_number: int
    prompt_text: str
    prompt_tokens: int = 0
    response_text: str = ""
    response_tokens: int = 0
    generated_code: str = ""
    accuracy_at_turn: float = 0.0
    timestamp: float = 0.0


class Session(BaseModel):
    id: str
    challenge_id: str
    mode: str = "arena"  # arena, practice
    status: str = "active"  # active, completed
    model_used: str = ""
    started_at: float = 0.0
    completed_at: float | None = None
    total_tokens: int = 0
    total_turns: int = 0
    turns: list[Turn] = []
    # Prompt for the turn currently in progress (shown in chat before response is ready)
    current_prompt: str | None = None
    # Agent run: ordered list of thinking-trace steps (step, elapsed_ms, timestamp, **kwargs)
    thinking_trace: list[dict] = []
    # Scores (populated on completion)
    accuracy_score: float | None = None
    speed_score: float | None = None
    token_score: float | None = None
    turn_score: float | None = None
    composite_score: float | None = None
    final_code: str = ""
    username: str = "anonymous"


class LeaderboardEntry(BaseModel):
    username: str
    composite_score: int
    accuracy_score: int
    speed_score: int
    challenge_id: str
    challenge_title: str
    total_turns: int
    total_tokens: int
    completed_at: float


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_sessions: dict[str, Session] = {}
_leaderboard: list[LeaderboardEntry] = []


def create_session(challenge_id: str, model: str, username: str = "anonymous") -> Session:
    session = Session(
        id=str(uuid.uuid4()),
        challenge_id=challenge_id,
        model_used=model,
        started_at=time.time(),
        username=username,
    )
    _sessions[session.id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def add_turn(session_id: str, turn: Turn) -> Session | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    session.turns.append(turn)
    session.total_turns = len(session.turns)
    session.total_tokens += turn.prompt_tokens + turn.response_tokens
    session.final_code = turn.generated_code
    return session


def append_trace(session_id: str, step: str, elapsed_ms: int, **kwargs: Any) -> None:
    """Append a thinking-trace entry for agent runs (used by agent_runner._trace)."""
    session = _sessions.get(session_id)
    if session is None:
        return
    session.thinking_trace.append({
        "step": step,
        "elapsed_ms": elapsed_ms,
        "timestamp": time.time(),
        **kwargs,
    })


def complete_session(session_id: str, scores: dict) -> Session | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    session.status = "completed"
    session.completed_at = time.time()
    session.accuracy_score = scores.get("accuracy_score")
    session.speed_score = scores.get("speed_score")
    session.token_score = scores.get("token_score")
    session.turn_score = scores.get("turn_score")
    session.composite_score = scores.get("composite_score")
    return session


def add_to_leaderboard(entry: LeaderboardEntry) -> None:
    _leaderboard.append(entry)
    _leaderboard.sort(key=lambda e: e.composite_score, reverse=True)


def get_leaderboard(
    limit: int = 50,
    category: str | None = None,
) -> list[LeaderboardEntry]:
    entries = _leaderboard
    if category:
        entries = [e for e in entries if e.challenge_id.startswith(category)]
    return entries[:limit]
