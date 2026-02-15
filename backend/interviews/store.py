"""Supabase-backed store for interview rooms and sessions.

Replaces the original in-memory dict store so that interview data
persists across server restarts and works correctly in production.
"""

import json
import logging
import secrets
import string
import time
import uuid
from datetime import datetime, timezone

from database import get_supabase_client

from .models import (
    InterviewRoom,
    InterviewChallenge,
    InterviewConfig,
    InterviewSession,
    InterviewTurn,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_invite_code(length: int = 8) -> str:
    """Generate a short, URL-safe invite code."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _ts_to_float(ts: str | None) -> float:
    """Convert an ISO-8601 timestamp string (from Supabase) to epoch float."""
    if ts is None:
        return 0.0
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def _float_to_iso(epoch: float) -> str:
    """Convert epoch float to ISO-8601 string for Supabase."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _row_to_room(row: dict) -> InterviewRoom:
    """Convert a Supabase row to an InterviewRoom model."""
    config_data = row.get("config") or {}
    if isinstance(config_data, str):
        config_data = json.loads(config_data)

    challenges_data = row.get("challenges") or []
    if isinstance(challenges_data, str):
        challenges_data = json.loads(challenges_data)

    challenges = []
    for ch in challenges_data:
        challenges.append(InterviewChallenge(
            id=ch["id"],
            title=ch["title"],
            description=ch["description"],
            category=ch["category"],
            starter_code=ch.get("starter_code"),
            solution_code=ch.get("solution_code"),
            test_cases=ch.get("test_cases"),
            reference_html=ch.get("reference_html"),
            sort_order=ch.get("sort_order", 0),
        ))

    return InterviewRoom(
        id=str(row["id"]),
        created_by=row["created_by"],
        title=row["title"],
        company_name=row.get("company_name") or "",
        invite_code=row["invite_code"],
        config=InterviewConfig(**config_data),
        challenges=challenges,
        status=row.get("status") or "pending",
        created_at=_ts_to_float(row.get("created_at")),
    )


def _row_to_turn(row: dict) -> InterviewTurn:
    """Convert a Supabase row to an InterviewTurn model."""
    return InterviewTurn(
        turn_number=row["turn_number"],
        prompt_text=row["prompt_text"],
        response_text=row.get("response_text") or "",
        generated_code=row.get("generated_code") or "",
        prompt_tokens=row.get("prompt_tokens") or 0,
        response_tokens=row.get("response_tokens") or 0,
        timestamp=_ts_to_float(row.get("timestamp")),
    )


def _row_to_session(
    row: dict,
    turns: list[InterviewTurn] | None = None,
) -> InterviewSession:
    """Convert a Supabase row to an InterviewSession model."""
    completed_at_raw = row.get("completed_at")
    return InterviewSession(
        id=str(row["id"]),
        room_id=str(row["room_id"]),
        challenge_id=row["challenge_id"],
        candidate_name=row["candidate_name"],
        status=row.get("status") or "active",
        started_at=_ts_to_float(row.get("started_at")),
        completed_at=_ts_to_float(completed_at_raw) if completed_at_raw else None,
        total_tokens=row.get("total_tokens") or 0,
        total_turns=row.get("total_turns") or 0,
        accuracy=row.get("accuracy") or 0.0,
        composite_score=row.get("composite_score") or 0,
        turns=turns or [],
        final_code=row.get("final_code") or "",
    )


# ---------------------------------------------------------------------------
# Room CRUD
# ---------------------------------------------------------------------------


def create_room(
    created_by: str,
    title: str,
    company_name: str = "",
    config: InterviewConfig | None = None,
) -> InterviewRoom:
    supabase = get_supabase_client()
    if not supabase:
        raise RuntimeError("Supabase not configured — interview persistence disabled")

    cfg = config or InterviewConfig()
    invite_code = _generate_invite_code()

    row_data = {
        "created_by": created_by,
        "title": title,
        "company_name": company_name,
        "invite_code": invite_code,
        "config": cfg.model_dump(),
        "challenges": [],
        "status": "pending",
    }

    response = supabase.table("interview_rooms").insert(row_data).execute()
    if not response.data:
        raise RuntimeError("Failed to create interview room in database")

    return _row_to_room(response.data[0])


def get_room(room_id: str) -> InterviewRoom | None:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("interview_rooms")
            .select("*")
            .eq("id", room_id)
            .limit(1)
            .execute()
        )
        if response.data:
            return _row_to_room(response.data[0])
        return None
    except Exception as e:
        logger.error("Error fetching room %s: %s", room_id, e)
        return None


def get_room_by_invite(invite_code: str) -> InterviewRoom | None:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("interview_rooms")
            .select("*")
            .eq("invite_code", invite_code)
            .limit(1)
            .execute()
        )
        if response.data:
            return _row_to_room(response.data[0])
        return None
    except Exception as e:
        logger.error("Error fetching room by invite %s: %s", invite_code, e)
        return None


def update_room(
    room_id: str,
    title: str | None = None,
    company_name: str | None = None,
    config: InterviewConfig | None = None,
) -> InterviewRoom | None:
    supabase = get_supabase_client()
    if not supabase:
        return None

    updates: dict = {}
    if title is not None:
        updates["title"] = title
    if company_name is not None:
        updates["company_name"] = company_name
    if config is not None:
        updates["config"] = config.model_dump()

    if not updates:
        return get_room(room_id)

    try:
        response = (
            supabase.table("interview_rooms")
            .update(updates)
            .eq("id", room_id)
            .execute()
        )
        if response.data:
            return _row_to_room(response.data[0])
        return None
    except Exception as e:
        logger.error("Error updating room %s: %s", room_id, e)
        return None


def complete_room(room_id: str) -> InterviewRoom | None:
    return _update_room_status(room_id, "completed")


def _update_room_status(room_id: str, status: str) -> InterviewRoom | None:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("interview_rooms")
            .update({"status": status})
            .eq("id", room_id)
            .execute()
        )
        if response.data:
            return _row_to_room(response.data[0])
        return None
    except Exception as e:
        logger.error("Error updating room status %s: %s", room_id, e)
        return None


def list_rooms(created_by: str | None = None) -> list[InterviewRoom]:
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        query = supabase.table("interview_rooms").select("*")
        if created_by:
            query = query.eq("created_by", created_by)
        query = query.order("created_at", desc=True)
        response = query.execute()
        return [_row_to_room(row) for row in (response.data or [])]
    except Exception as e:
        logger.error("Error listing rooms: %s", e)
        return []


# ---------------------------------------------------------------------------
# Challenge management (stored as JSONB array on the room row)
# ---------------------------------------------------------------------------


def _save_room_challenges(
    room_id: str, challenges: list[InterviewChallenge]
) -> bool:
    """Persist the challenges JSONB array back to the room row."""
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        challenges_data = [ch.model_dump() for ch in challenges]
        supabase.table("interview_rooms").update(
            {"challenges": challenges_data}
        ).eq("id", room_id).execute()
        return True
    except Exception as e:
        logger.error("Error saving challenges for room %s: %s", room_id, e)
        return False


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
    room = get_room(room_id)
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

    if _save_room_challenges(room_id, room.challenges):
        return challenge
    return None


def update_challenge(
    room_id: str,
    challenge_id: str,
    **kwargs: object,
) -> InterviewChallenge | None:
    room = get_room(room_id)
    if room is None:
        return None

    for ch in room.challenges:
        if ch.id == challenge_id:
            for key, value in kwargs.items():
                if value is not None and hasattr(ch, key):
                    setattr(ch, key, value)
            _save_room_challenges(room_id, room.challenges)
            return ch
    return None


def remove_challenge(room_id: str, challenge_id: str) -> bool:
    room = get_room(room_id)
    if room is None:
        return False

    before = len(room.challenges)
    room.challenges = [c for c in room.challenges if c.id != challenge_id]
    if len(room.challenges) < before:
        _save_room_challenges(room_id, room.challenges)
        return True
    return False


def get_challenge(room_id: str, challenge_id: str) -> InterviewChallenge | None:
    room = get_room(room_id)
    if room is None:
        return None
    for ch in room.challenges:
        if ch.id == challenge_id:
            return ch
    return None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def _load_turns_for_session(session_id: str) -> list[InterviewTurn]:
    """Load all turns for a session from Supabase, ordered by turn_number."""
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        response = (
            supabase.table("interview_turns")
            .select("*")
            .eq("session_id", session_id)
            .order("turn_number")
            .execute()
        )
        return [_row_to_turn(row) for row in (response.data or [])]
    except Exception as e:
        logger.error("Error loading turns for session %s: %s", session_id, e)
        return []


def create_session(
    room_id: str,
    challenge_id: str,
    candidate_name: str,
) -> InterviewSession | None:
    room = get_room(room_id)
    if room is None:
        return None

    # Verify challenge exists in this room
    found = any(ch.id == challenge_id for ch in room.challenges)
    if not found:
        return None

    # Mark room as active if first session
    if room.status == "pending":
        _update_room_status(room_id, "active")

    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        row_data = {
            "room_id": room_id,
            "challenge_id": challenge_id,
            "candidate_name": candidate_name,
            "status": "active",
            "total_tokens": 0,
            "total_turns": 0,
            "accuracy": 0.0,
            "composite_score": 0,
            "final_code": "",
        }
        response = (
            supabase.table("interview_sessions").insert(row_data).execute()
        )
        if not response.data:
            return None
        return _row_to_session(response.data[0], turns=[])
    except Exception as e:
        logger.error("Error creating interview session: %s", e)
        return None


def get_session(session_id: str) -> InterviewSession | None:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("interview_sessions")
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        turns = _load_turns_for_session(session_id)
        return _row_to_session(response.data[0], turns=turns)
    except Exception as e:
        logger.error("Error fetching session %s: %s", session_id, e)
        return None


def get_sessions_for_room(room_id: str) -> list[InterviewSession]:
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        response = (
            supabase.table("interview_sessions")
            .select("*")
            .eq("room_id", room_id)
            .order("started_at")
            .execute()
        )
        sessions = []
        for row in response.data or []:
            sid = str(row["id"])
            turns = _load_turns_for_session(sid)
            sessions.append(_row_to_session(row, turns=turns))
        return sessions
    except Exception as e:
        logger.error("Error fetching sessions for room %s: %s", room_id, e)
        return []


def add_turn(session_id: str, turn: InterviewTurn) -> InterviewSession | None:
    """Insert a turn row and update session aggregates. Returns the updated session."""
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Insert the turn row
        turn_data = {
            "session_id": session_id,
            "turn_number": turn.turn_number,
            "prompt_text": turn.prompt_text,
            "response_text": turn.response_text,
            "generated_code": turn.generated_code,
            "prompt_tokens": turn.prompt_tokens,
            "response_tokens": turn.response_tokens,
        }
        supabase.table("interview_turns").insert(turn_data).execute()

        # 2. Fetch current session totals
        sess_resp = (
            supabase.table("interview_sessions")
            .select("total_tokens, total_turns")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        if not sess_resp.data:
            return None

        current = sess_resp.data[0]
        new_total_tokens = (
            (current.get("total_tokens") or 0)
            + turn.prompt_tokens
            + turn.response_tokens
        )
        new_total_turns = (current.get("total_turns") or 0) + 1

        # 3. Update session aggregates
        supabase.table("interview_sessions").update({
            "total_tokens": new_total_tokens,
            "total_turns": new_total_turns,
            "final_code": turn.generated_code,
        }).eq("id", session_id).execute()

        # 4. Return the full updated session
        return get_session(session_id)
    except Exception as e:
        logger.error("Error adding turn to session %s: %s", session_id, e)
        return None


def update_session_accuracy(session_id: str, accuracy: float) -> None:
    """Update the accuracy field on a session (e.g. after running tests)."""
    supabase = get_supabase_client()
    if not supabase:
        return
    try:
        supabase.table("interview_sessions").update(
            {"accuracy": accuracy}
        ).eq("id", session_id).execute()
    except Exception as e:
        logger.error("Error updating session accuracy %s: %s", session_id, e)


def complete_session(
    session_id: str,
    accuracy: float = 0.0,
    composite_score: int = 0,
) -> InterviewSession | None:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("interview_sessions")
            .update({
                "status": "completed",
                "completed_at": _float_to_iso(time.time()),
                "accuracy": accuracy,
                "composite_score": composite_score,
            })
            .eq("id", session_id)
            .execute()
        )
        if not response.data:
            return None
        turns = _load_turns_for_session(session_id)
        return _row_to_session(response.data[0], turns=turns)
    except Exception as e:
        logger.error("Error completing session %s: %s", session_id, e)
        return None
