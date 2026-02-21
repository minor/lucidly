"""FastAPI router for Interview mode endpoints."""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import settings, MODEL_PRICING
from evaluation import compute_composite_score

from .models import (
    CreateRoomRequest,
    AddChallengeRequest,
    UpdateChallengeRequest,
    UpdateRoomRequest,
    StartSessionRequest,
    SubmitPromptRequest,
    InterviewTestCase,
    InterviewTurn,
)
from . import store
from . import realtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


# ---------------------------------------------------------------------------
# Room CRUD
# ---------------------------------------------------------------------------


@router.post("")
async def create_room(req: CreateRoomRequest):
    """Create a new interview room. Returns the room with its invite code."""
    room = store.create_room(
        created_by=req.created_by,
        title=req.title,
        company_name=req.company_name,
        config=req.config,
    )
    return room


@router.get("")
async def list_rooms(created_by: str | None = None):
    """List interview rooms, optionally filtered by creator."""
    return store.list_rooms(created_by=created_by)


# IMPORTANT: Static path /invite/ must come BEFORE dynamic /{room_id}
@router.get("/invite/{invite_code}")
async def get_room_by_invite(invite_code: str):
    """Get a room by its invite code (for candidates joining)."""
    room = store.get_room_by_invite(invite_code)
    if room is None:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return room


@router.get("/{room_id}")
async def get_room(room_id: str):
    """Get a room by its ID (for interviewer dashboard)."""
    room = store.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/{room_id}")
async def update_room(room_id: str, req: UpdateRoomRequest):
    """Update room settings."""
    room = store.update_room(
        room_id,
        title=req.title,
        company_name=req.company_name,
        config=req.config,
    )
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.post("/{room_id}/complete")
async def complete_room(room_id: str):
    """Mark a room as completed."""
    room = store.complete_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


# ---------------------------------------------------------------------------
# Challenge management within a room
# ---------------------------------------------------------------------------


@router.post("/{room_id}/challenges")
async def add_challenge(room_id: str, req: AddChallengeRequest):
    """Add a challenge to an interview room."""
    challenge = store.add_challenge(
        room_id=room_id,
        title=req.title,
        description=req.description,
        category=req.category,
        starter_code=req.starter_code,
        solution_code=req.solution_code,
        test_cases=[tc.model_dump() for tc in req.test_cases] if req.test_cases else None,
        reference_html=req.reference_html,
    )
    if challenge is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return challenge


@router.patch("/{room_id}/challenges/{challenge_id}")
async def update_challenge(room_id: str, challenge_id: str, req: UpdateChallengeRequest):
    """Update an existing challenge."""
    updates = req.model_dump(exclude_none=True)
    # Serialize test_cases if present
    if "test_cases" in updates and updates["test_cases"] is not None:
        updates["test_cases"] = [
            tc.model_dump() if isinstance(tc, InterviewTestCase) else tc
            for tc in updates["test_cases"]
        ]
    challenge = store.update_challenge(room_id, challenge_id, **updates)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Room or challenge not found")
    return challenge


@router.delete("/{room_id}/challenges/{challenge_id}")
async def remove_challenge(room_id: str, challenge_id: str):
    """Remove a challenge from a room."""
    removed = store.remove_challenge(room_id, challenge_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Room or challenge not found")
    return {"status": "removed"}


# ---------------------------------------------------------------------------
# Interview sessions (candidate flow)
# ---------------------------------------------------------------------------


@router.post("/{room_id}/sessions")
async def start_session(room_id: str, req: StartSessionRequest):
    """Candidate starts a session for a specific challenge in a room."""
    room = store.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status == "completed":
        raise HTTPException(status_code=400, detail="Interview room is closed")

    session = store.create_session(
        room_id=room_id,
        challenge_id=req.challenge_id,
        candidate_name=req.candidate_name,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Challenge not found in this room")

    # Broadcast to observers
    await realtime.broadcast(room_id, {
        "type": "session_started",
        "session_id": session.id,
        "candidate_name": req.candidate_name,
        "challenge_id": req.challenge_id,
        "timestamp": time.time(),
    })

    return session


@router.get("/{room_id}/sessions")
async def list_sessions(room_id: str):
    """List all sessions in a room (for interviewer)."""
    return store.get_sessions_for_room(room_id)


@router.get("/{room_id}/sessions/{session_id}")
async def get_session(room_id: str, session_id: str):
    """Get session state."""
    session = store.get_session(session_id)
    if session is None or session.room_id != room_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{room_id}/sessions/{session_id}/prompt")
async def submit_prompt(room_id: str, session_id: str, req: SubmitPromptRequest):
    """Candidate submits a prompt. Streams LLM response via SSE."""
    session = store.get_session(session_id)
    if session is None or session.room_id != room_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    room = store.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check token budget
    if room.config.max_token_budget and session.total_tokens >= room.config.max_token_budget:
        raise HTTPException(status_code=400, detail="Token budget exceeded")

    # Check allowed models
    model = req.model or settings.default_model
    if room.config.allowed_models and model not in room.config.allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Model {model} is not allowed. Allowed: {room.config.allowed_models}",
        )

    # Build conversation history
    history: list[dict] = []
    for turn in session.turns:
        history.append({"role": "user", "content": turn.prompt_text})
        history.append({"role": "assistant", "content": turn.response_text})

    # Broadcast prompt to observers
    await realtime.broadcast(room_id, {
        "type": "prompt_submitted",
        "session_id": session_id,
        "prompt": req.prompt,
        "turn_number": len(session.turns) + 1,
        "timestamp": time.time(),
    })

    # Get the challenge for system prompt context
    challenge = store.get_challenge(room_id, session.challenge_id)
    system_prompt = "You are a code generation assistant. Generate clean, working code based on the user's prompt. Provide the code in markdown code blocks."
    if challenge and challenge.category == "frontend":
        system_prompt = "You are a frontend code generation assistant. Generate clean, working HTML/CSS/JavaScript or React code. Always provide complete, self-contained code in markdown code blocks."

    from llm import LLM
    llm_instance = LLM(
        model=model,
        system_prompt=system_prompt,
    )

    async def generate():
        full_response = ""
        input_tokens = 0
        output_tokens = 0

        try:
            # GPT-5 Mini and Nano require temperature=1
            temperature = 1.0 if model in ["gpt-5-mini", "gpt-5-nano"] else None

            async for chunk in llm_instance.stream(
                req.prompt,
                conversation_history=history if history else None,
                temperature=temperature,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                # Broadcast chunk to observers
                await realtime.broadcast(room_id, {
                    "type": "response_chunk",
                    "session_id": session_id,
                    "chunk": chunk,
                })

            # Extract code from response
            generated_code = LLM.extract_code_blocks(full_response)

            # Estimate tokens
            est_prompt_tokens = len(req.prompt.split()) * 2
            est_response_tokens = len(full_response.split()) * 2

            # Calculate cost
            pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
            cost = (est_prompt_tokens * pricing["input"] + est_response_tokens * pricing["output"]) / 1_000_000

            # Record turn
            turn_obj = InterviewTurn(
                turn_number=len(session.turns) + 1,
                prompt_text=req.prompt,
                response_text=full_response,
                generated_code=generated_code,
                prompt_tokens=est_prompt_tokens,
                response_tokens=est_response_tokens,
                timestamp=time.time(),
            )
            updated_session = store.add_turn(session_id, turn_obj)
            _total_tokens = updated_session.total_tokens if updated_session else session.total_tokens + est_prompt_tokens + est_response_tokens
            _total_turns = updated_session.total_turns if updated_session else session.total_turns + 1

            # Broadcast turn complete to observers
            await realtime.broadcast(room_id, {
                "type": "turn_complete",
                "session_id": session_id,
                "turn_number": _total_turns,
                "generated_code": generated_code,
                "total_tokens": _total_tokens,
                "total_turns": _total_turns,
                "timestamp": time.time(),
            })

            yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'generated_code': generated_code, 'input_tokens': est_prompt_tokens, 'output_tokens': est_response_tokens, 'cost': cost, 'total_tokens': _total_tokens, 'total_turns': _total_turns})}\n\n"

        except Exception as e:
            logger.error("Interview prompt streaming error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{room_id}/sessions/{session_id}/complete")
async def complete_session(room_id: str, session_id: str):
    """Mark a session as completed and compute scores."""
    session = store.get_session(session_id)
    if session is None or session.room_id != room_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session already completed")

    room = store.get_room(room_id)
    challenge = store.get_challenge(room_id, session.challenge_id) if room else None

    elapsed = time.time() - session.started_at

    # Compute score
    scores = compute_composite_score(
        accuracy=session.accuracy,
        elapsed_sec=elapsed,
        total_tokens=session.total_tokens,
        total_turns=session.total_turns,
        difficulty="medium",
    )

    completed = store.complete_session(
        session_id,
        accuracy=session.accuracy,
        composite_score=scores.get("composite_score", 0),
    )

    # Broadcast completion to observers
    await realtime.broadcast(room_id, {
        "type": "session_completed",
        "session_id": session_id,
        "scores": scores,
        "timestamp": time.time(),
    })

    return {
        "session": completed,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Run tests for interview challenges (coding)
# ---------------------------------------------------------------------------


@router.post("/{room_id}/sessions/{session_id}/run-tests")
async def run_tests(room_id: str, session_id: str, code: str | None = None):
    """Run code against a challenge's test cases. Uses the session's latest code if none provided."""
    session = store.get_session(session_id)
    if session is None or session.room_id != room_id:
        raise HTTPException(status_code=404, detail="Session not found")

    challenge = store.get_challenge(room_id, session.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not challenge.test_cases:
        raise HTTPException(status_code=400, detail="Challenge has no test cases")

    test_code = code or session.final_code
    if not test_code:
        raise HTTPException(status_code=400, detail="No code to test")

    # Use the same test execution as arena mode
    from evaluation import run_function_tests_detailed
    from sandbox import create_sandbox, terminate_sandbox

    sandbox_id = None
    try:
        sandbox_id = await create_sandbox()
        test_dicts = (
            [tc if isinstance(tc, dict) else tc.model_dump() for tc in challenge.test_cases]
        )
        raw_results = await run_function_tests_detailed(sandbox_id, test_code, test_dicts)
        results = raw_results
        passed_count = sum(1 for r in results if r.get("passed", False))
        total_count = len(results)

        # Update session accuracy (persisted to Supabase)
        if total_count > 0:
            store.update_session_accuracy(session_id, passed_count / total_count)

        # Broadcast test results to observers
        await realtime.broadcast(room_id, {
            "type": "test_results",
            "session_id": session_id,
            "passed_count": passed_count,
            "total_count": total_count,
            "results": results,
            "timestamp": time.time(),
        })

        return {
            "results": results,
            "all_passed": passed_count == total_count,
            "passed_count": passed_count,
            "total_count": total_count,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if sandbox_id:
            try:
                await terminate_sandbox(sandbox_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Observation (SSE stream for interviewers)
# ---------------------------------------------------------------------------


@router.get("/{room_id}/observe")
async def observe_room(room_id: str):
    """SSE stream for live observation of an interview room."""
    room = store.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    queue = realtime.subscribe(room_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            realtime.unsubscribe(room_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@router.get("/{room_id}/report")
async def get_report(room_id: str):
    """Get assessment report for all sessions in a room."""
    room = store.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    sessions = store.get_sessions_for_room(room_id)
    challenges = {ch.id: ch for ch in room.challenges}

    report = {
        "room": room,
        "sessions": [],
    }

    for session in sessions:
        challenge = challenges.get(session.challenge_id)
        elapsed = (session.completed_at or time.time()) - session.started_at

        session_report = {
            "session": session,
            "challenge_title": challenge.title if challenge else "Unknown",
            "challenge_category": challenge.category if challenge else "Unknown",
            "elapsed_sec": elapsed,
            "metrics": {
                "total_turns": session.total_turns,
                "total_tokens": session.total_tokens,
                "accuracy": session.accuracy,
                "composite_score": session.composite_score,
            },
            "turns": [t.model_dump() for t in session.turns],
        }
        report["sessions"].append(session_report)

    return report
