"""Lucidly backend — FastAPI application."""

import json
import time

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from llm import LLM
from challenges import get_all_challenges, get_challenge_by_id
from sessions import (
    create_session,
    get_session,
    add_turn,
    complete_session,
    add_to_leaderboard,
    get_leaderboard,
    Turn,
    LeaderboardEntry,
)
from scoring import (
    compute_composite_score,
    compute_accuracy_function,
    compute_accuracy_text,
    run_function_tests,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Lucidly", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default LLM instance (can be overridden per-request)
llm = LLM()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    challenge_id: str
    model: str | None = None
    username: str = "anonymous"


class PromptRequest(BaseModel):
    prompt: str
    model: str | None = None


class PromptResponse(BaseModel):
    turn_number: int
    response_text: str
    generated_code: str
    prompt_tokens: int
    response_tokens: int
    accuracy: float
    test_results: list[bool] | None = None


# ---------------------------------------------------------------------------
# Challenge endpoints
# ---------------------------------------------------------------------------


@app.get("/api/challenges")
async def list_challenges(category: str | None = None, difficulty: str | None = None):
    challenges = get_all_challenges()
    if category:
        challenges = [c for c in challenges if c.category == category]
    if difficulty:
        challenges = [c for c in challenges if c.difficulty == difficulty]
    return challenges


@app.get("/api/challenges/{challenge_id}")
async def get_challenge(challenge_id: str):
    challenge = get_challenge_by_id(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------


@app.post("/api/sessions")
async def start_session(req: CreateSessionRequest):
    challenge = get_challenge_by_id(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    model = req.model or settings.default_model
    session = create_session(req.challenge_id, model, req.username)
    return {"session_id": session.id, "challenge": challenge}


@app.get("/api/sessions/{session_id}")
async def get_session_state(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/sessions/{session_id}/prompt")
async def submit_prompt(session_id: str, req: PromptRequest):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    challenge = get_challenge_by_id(session.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Build conversation history from previous turns
    history: list[dict] = []
    for turn in session.turns:
        history.append({"role": "user", "content": turn.prompt_text})
        history.append({"role": "assistant", "content": turn.response_text})

    # Call LLM
    model = req.model or session.model_used
    llm_instance = LLM(model=model) if model != llm.model else llm
    response = await llm_instance.generate(
        req.prompt,
        conversation_history=history if history else None,
    )

    # Compute accuracy for this turn
    accuracy = 0.0
    test_results = None

    if challenge.category == "function" and challenge.test_suite:
        test_dicts = [t.model_dump() for t in challenge.test_suite]
        test_results = run_function_tests(response.generated_code, test_dicts)
        accuracy = compute_accuracy_function(test_results)
    elif challenge.target_code:
        accuracy = compute_accuracy_text(response.generated_code, challenge.target_code)

    # Record turn
    turn = Turn(
        turn_number=len(session.turns) + 1,
        prompt_text=req.prompt,
        prompt_tokens=response.prompt_tokens,
        response_text=response.response_text,
        response_tokens=response.response_tokens,
        generated_code=response.generated_code,
        accuracy_at_turn=accuracy,
        timestamp=time.time(),
    )
    add_turn(session_id, turn)

    return PromptResponse(
        turn_number=turn.turn_number,
        response_text=response.response_text,
        generated_code=response.generated_code,
        prompt_tokens=response.prompt_tokens,
        response_tokens=response.response_tokens,
        accuracy=accuracy,
        test_results=test_results,
    )


@app.post("/api/sessions/{session_id}/complete")
async def finish_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session already completed")

    challenge = get_challenge_by_id(session.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Get final accuracy from last turn
    accuracy = 0.0
    if session.turns:
        accuracy = session.turns[-1].accuracy_at_turn

    elapsed = time.time() - session.started_at
    scores = compute_composite_score(
        accuracy=accuracy,
        elapsed_sec=elapsed,
        total_tokens=session.total_tokens,
        total_turns=session.total_turns,
    )

    completed = complete_session(session_id, scores)

    # Add to leaderboard
    if completed:
        add_to_leaderboard(
            LeaderboardEntry(
                username=completed.username,
                composite_score=scores["composite_score"],
                accuracy_score=scores["accuracy_score"],
                speed_score=scores["speed_score"],
                challenge_id=completed.challenge_id,
                challenge_title=challenge.title,
                total_turns=completed.total_turns,
                total_tokens=completed.total_tokens,
                completed_at=completed.completed_at or time.time(),
            )
        )

    return {
        "session": completed,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


@app.get("/api/leaderboard")
async def leaderboard(limit: int = 50, category: str | None = None):
    return get_leaderboard(limit=limit, category=category)


# ---------------------------------------------------------------------------
# WebSocket — streaming LLM responses
# ---------------------------------------------------------------------------


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str):
    await ws.accept()

    session = get_session(session_id)
    if session is None:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close()
        return

    challenge = get_challenge_by_id(session.challenge_id)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "prompt":
                prompt_text = msg.get("content", "")
                model = msg.get("model") or session.model_used

                # Build conversation history
                history: list[dict] = []
                for turn in session.turns:
                    history.append({"role": "user", "content": turn.prompt_text})
                    history.append({"role": "assistant", "content": turn.response_text})

                llm_instance = LLM(model=model) if model != llm.model else llm

                # Stream response
                full_response = ""
                async for chunk in llm_instance.stream(
                    prompt_text,
                    conversation_history=history if history else None,
                ):
                    full_response += chunk
                    await ws.send_json({"type": "stream", "content": chunk})

                generated_code = LLM.extract_code_blocks(full_response)

                # Compute accuracy
                accuracy = 0.0
                test_results = None
                if challenge and challenge.category == "function" and challenge.test_suite:
                    test_dicts = [t.model_dump() for t in challenge.test_suite]
                    test_results = run_function_tests(generated_code, test_dicts)
                    accuracy = compute_accuracy_function(test_results)
                elif challenge and challenge.target_code:
                    accuracy = compute_accuracy_text(generated_code, challenge.target_code)

                # We don't have token counts in streaming mode (most APIs
                # don't return them mid-stream), so estimate from text length.
                est_prompt_tokens = len(prompt_text.split()) * 2
                est_response_tokens = len(full_response.split()) * 2

                turn = Turn(
                    turn_number=len(session.turns) + 1,
                    prompt_text=prompt_text,
                    prompt_tokens=est_prompt_tokens,
                    response_text=full_response,
                    response_tokens=est_response_tokens,
                    generated_code=generated_code,
                    accuracy_at_turn=accuracy,
                    timestamp=time.time(),
                )
                add_turn(session_id, turn)

                await ws.send_json({
                    "type": "complete",
                    "turn_number": turn.turn_number,
                    "generated_code": generated_code,
                    "accuracy": accuracy,
                    "test_results": test_results,
                    "prompt_tokens": est_prompt_tokens,
                    "response_tokens": est_response_tokens,
                })

    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.default_model}
