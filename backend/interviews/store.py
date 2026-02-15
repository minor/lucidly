"""In-memory store for interview rooms and sessions (MVP)."""

import time
import uuid
import secrets
import string

from .models import (
    InterviewRoom,
    InterviewChallenge,
    InterviewConfig,
    InterviewSession,
    InterviewTurn,
)

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_rooms: dict[str, InterviewRoom] = {}
_rooms_by_invite: dict[str, str] = {}  # invite_code -> room_id
_sessions: dict[str, InterviewSession] = {}
_sessions_by_room: dict[str, list[str]] = {}  # room_id -> [session_id, ...]


def _generate_invite_code(length: int = 8) -> str:
    """Generate a short, URL-safe invite code."""
    alphabet = string.ascii_lowercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if code not in _rooms_by_invite:
            return code


# ---------------------------------------------------------------------------
# Room CRUD
# ---------------------------------------------------------------------------


def create_room(
    created_by: str,
    title: str,
    company_name: str = "",
    config: InterviewConfig | None = None,
) -> InterviewRoom:
    room = InterviewRoom(
        id=str(uuid.uuid4()),
        created_by=created_by,
        title=title,
        company_name=company_name,
        invite_code=_generate_invite_code(),
        config=config or InterviewConfig(),
        created_at=time.time(),
    )
    _rooms[room.id] = room
    _rooms_by_invite[room.invite_code] = room.id
    _sessions_by_room[room.id] = []
    return room


def get_room(room_id: str) -> InterviewRoom | None:
    return _rooms.get(room_id)


def get_room_by_invite(invite_code: str) -> InterviewRoom | None:
    room_id = _rooms_by_invite.get(invite_code)
    if room_id is None:
        return None
    return _rooms.get(room_id)


def update_room(
    room_id: str,
    title: str | None = None,
    company_name: str | None = None,
    config: InterviewConfig | None = None,
) -> InterviewRoom | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    if title is not None:
        room.title = title
    if company_name is not None:
        room.company_name = company_name
    if config is not None:
        room.config = config
    return room


def complete_room(room_id: str) -> InterviewRoom | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    room.status = "completed"
    return room


def list_rooms(created_by: str | None = None) -> list[InterviewRoom]:
    rooms = list(_rooms.values())
    if created_by:
        rooms = [r for r in rooms if r.created_by == created_by]
    rooms.sort(key=lambda r: r.created_at, reverse=True)
    return rooms


# ---------------------------------------------------------------------------
# Challenge management (within a room)
# ---------------------------------------------------------------------------


def add_challenge(
    room_id: str,
    title: str,
    description: str,
    category: str,
    starter_code: str | None = None,
    solution_code: str | None = None,
    test_cases: list | None = None,
    reference_html: str | None = None,
) -> InterviewChallenge | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    challenge = InterviewChallenge(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        category=category,
        starter_code=starter_code,
        solution_code=solution_code,
        test_cases=test_cases,
        reference_html=reference_html,
        sort_order=len(room.challenges),
    )
    room.challenges.append(challenge)
    return challenge


def update_challenge(
    room_id: str,
    challenge_id: str,
    **kwargs: object,
) -> InterviewChallenge | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    for ch in room.challenges:
        if ch.id == challenge_id:
            for key, value in kwargs.items():
                if value is not None and hasattr(ch, key):
                    setattr(ch, key, value)
            return ch
    return None


def remove_challenge(room_id: str, challenge_id: str) -> bool:
    room = _rooms.get(room_id)
    if room is None:
        return False
    before = len(room.challenges)
    room.challenges = [c for c in room.challenges if c.id != challenge_id]
    return len(room.challenges) < before


def get_challenge(room_id: str, challenge_id: str) -> InterviewChallenge | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    for ch in room.challenges:
        if ch.id == challenge_id:
            return ch
    return None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def create_session(
    room_id: str,
    challenge_id: str,
    candidate_name: str,
) -> InterviewSession | None:
    room = _rooms.get(room_id)
    if room is None:
        return None
    # Verify challenge exists in this room
    challenge = get_challenge(room_id, challenge_id)
    if challenge is None:
        return None
    # Mark room as active if first session
    if room.status == "pending":
        room.status = "active"
    session = InterviewSession(
        id=str(uuid.uuid4()),
        room_id=room_id,
        challenge_id=challenge_id,
        candidate_name=candidate_name,
        started_at=time.time(),
    )
    _sessions[session.id] = session
    _sessions_by_room.setdefault(room_id, []).append(session.id)
    return session


def get_session(session_id: str) -> InterviewSession | None:
    return _sessions.get(session_id)


def get_sessions_for_room(room_id: str) -> list[InterviewSession]:
    session_ids = _sessions_by_room.get(room_id, [])
    return [_sessions[sid] for sid in session_ids if sid in _sessions]


def add_turn(session_id: str, turn: InterviewTurn) -> InterviewSession | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    session.turns.append(turn)
    session.total_turns = len(session.turns)
    session.total_tokens += turn.prompt_tokens + turn.response_tokens
    session.final_code = turn.generated_code
    return session


def complete_session(
    session_id: str,
    accuracy: float = 0.0,
    composite_score: int = 0,
) -> InterviewSession | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    session.status = "completed"
    session.completed_at = time.time()
    session.accuracy = accuracy
    session.composite_score = composite_score
    return session
