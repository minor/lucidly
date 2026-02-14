"""Lucidly backend — FastAPI application."""

import json
import time
import httpx

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from llm import LLM
from challenges import get_all_challenges, get_challenge_by_id
from agents import get_all_agents, get_agent_by_id
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
from evaluation import (
    compute_composite_score,
    compute_accuracy_function,
    compute_accuracy_text,
    run_function_tests_detailed,
    TestGenerator,
    GeneratedTestSuite,
    ChallengeEvaluator,
)
from sandbox import create_sandbox, terminate_sandbox

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

# Test generator and evaluator instances
# TestGenerator uses Claude by default (configured in test_generator.py)
test_generator = TestGenerator()  # Will use Claude via create_claude_llm()
evaluator = ChallengeEvaluator()


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
    system_prompt: str | None = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None


class PromptResponse(BaseModel):
    turn_number: int
    response_text: str
    generated_code: str
    prompt_tokens: int
    response_tokens: int
    accuracy: float
    test_results: list[bool] | None = None
    evaluation_details: dict | None = None  # Additional evaluation details
    execution_output: str | None = None  # Output from code execution


class AgentRunRequest(BaseModel):
    agent_id: str
    challenge_id: str


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


@app.post("/api/challenges/{challenge_id}/generate-tests")
async def generate_tests_for_challenge(challenge_id: str):
    """
    Automatically generate test suite for a challenge.
    Returns the generated test suite with test cases tailored to the challenge type.
    """
    challenge = get_challenge_by_id(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    test_suite = await test_generator.generate_tests(challenge)
    return {
        "challenge_id": challenge_id,
        "test_suite": test_suite.model_dump(),
    }


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


def _require_agent_token_if_agent(session, request: Request) -> None:
    if not session.username.startswith("agent:"):
        return
    secret = settings.agent_internal_secret
    if not secret:
        return
    token = request.headers.get("X-Agent-Token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing agent token")


@app.post("/api/sessions/{session_id}/prompt")
async def submit_prompt(session_id: str, request: Request, req: PromptRequest):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    _require_agent_token_if_agent(session, request)
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
        system_prompt=req.system_prompt,
    )

    # Generate tests if not already present, then evaluate
    generated_test_suite = None
    # Only generate tests if challenge doesn't have a test suite
    # For function challenges, prefer existing test_suite if available
    if not challenge.test_suite:
        # Auto-generate tests for this challenge
        generated_test_suite = await test_generator.generate_tests(challenge)
    
    # Evaluate using the new evaluator system
    # The evaluator will use challenge.test_suite if available, otherwise generated_test_suite
    eval_result = await evaluator.evaluate(
        challenge,
        response.generated_code,
        generated_test_suite,
    )
    
    accuracy = eval_result.accuracy
    test_results = eval_result.test_results

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
        evaluation_details=eval_result.details,
        execution_output=eval_result.execution_output,
    )


@app.post("/api/sessions/{session_id}/complete")
async def finish_session(session_id: str, request: Request):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    _require_agent_token_if_agent(session, request)
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
# Agents (benchmark runs)
# ---------------------------------------------------------------------------


@app.get("/api/agents")
async def list_agents():
    return get_all_agents()


@app.post("/api/agent-runs")
async def start_agent_run(req: AgentRunRequest):
    agent = get_agent_by_id(req.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    challenge = get_challenge_by_id(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    username = f"agent:{agent.id}"
    session = create_session(req.challenge_id, agent.model, username)
    try:
        import modal
        fn = modal.Function.lookup(settings.modal_app_name, "run_agent")
        fn.spawn(
            session_id=session.id,
            challenge_id=req.challenge_id,
            agent_id=req.agent_id,
            backend_url=settings.backend_public_url,
            agent_token=settings.agent_internal_secret or "",
        )
    except Exception:
        # Modal not configured or deploy missing; frontend can still poll session
        pass
    return {"session_id": session.id, "challenge_id": req.challenge_id, "agent_id": req.agent_id}


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

                # Generate tests if needed and evaluate
                generated_test_suite = None
                if challenge and not challenge.test_suite:
                    generated_test_suite = await test_generator.generate_tests(challenge)
                
                # Evaluate using the new evaluator system
                accuracy = 0.0
                test_results = None
                eval_result = None
                if challenge:
                    eval_result = await evaluator.evaluate(
                        challenge,
                        generated_code,
                        generated_test_suite,
                    )
                    accuracy = eval_result.accuracy
                    test_results = eval_result.test_results

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
                    "evaluation_details": eval_result.details if eval_result else None,
                    "execution_output": eval_result.execution_output if eval_result else None,
                    "prompt_tokens": est_prompt_tokens,
                    "response_tokens": est_response_tokens,
                })

    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Chat endpoint — streaming chat with Claude Code API
# ---------------------------------------------------------------------------


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Stream chat responses from Claude Code API.
    Uses Server-Sent Events (SSE) for real-time streaming.
    Supports both Anthropic API directly and OpenAI-compatible APIs (like OpenRouter).
    """
    # Convert messages to Anthropic format (or OpenAI format if using OpenRouter)
    anthropic_messages = []
    for msg in req.messages:
        anthropic_messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    if not anthropic_messages or anthropic_messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")
    
    # Use Anthropic API directly if API key is set, otherwise fall back to OpenAI-compatible
    use_anthropic = bool(settings.anthropic_api_key)
    
    # Validate that we have at least one API key configured
    if not use_anthropic and not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="No API key configured. Please set either ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
        )
    
    # Use correct Anthropic model names
    # Valid models: claude-3-5-sonnet-20240620, claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
    model = req.model or ("claude-opus-4-6" if use_anthropic else "anthropic/claude-opus-4-6")
    
    async def generate():
        """Generator function for SSE streaming."""
        try:
            if use_anthropic:
                # Use Anthropic API directly
                async with httpx.AsyncClient(timeout=60.0) as client:
                    headers = {
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    }
                    
                    # Extract system message if present, otherwise use default
                    system_message = "You are a helpful AI assistant. Provide clear, concise, and helpful responses."
                    messages_for_api = anthropic_messages.copy()
                    
                    payload = {
                        "model": model,
                        "max_tokens": 16384,
                        "messages": messages_for_api,
                        "system": system_message,
                        "stream": True,
                    }
                    
                    async with client.stream(
                        "POST",
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            error_detail = error_text.decode()
                            # Provide more helpful error messages
                            if response.status_code == 401:
                                error_detail = f"Invalid or missing Anthropic API key. Please check your ANTHROPIC_API_KEY in .env file. Original error: {error_detail}"
                            elif response.status_code == 404:
                                error_detail = f"Model not found. Please check the model name. Valid models: claude-3-5-sonnet-20240620, claude-3-opus-20240229, claude-3-sonnet-20240229. Original error: {error_detail}"
                            # Can't raise HTTPException in streaming response, so yield error instead
                            yield f"data: {json.dumps({'type': 'error', 'message': error_detail})}\n\n"
                            return
                        
                        full_response = ""
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if data.get("type") == "content_block_delta":
                                        chunk = data.get("delta", {}).get("text", "")
                                        if chunk:
                                            full_response += chunk
                                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                                    elif data.get("type") == "message_stop":
                                        break
                                except json.JSONDecodeError:
                                    continue
                        
                        yield f"data: {json.dumps({'type': 'done', 'content': full_response})}\n\n"
            else:
                # Use OpenAI-compatible API (e.g., OpenRouter)
                conversation_history = []
                current_prompt = ""
                
                for msg in anthropic_messages:
                    if msg["role"] == "user":
                        if current_prompt:
                            conversation_history.append({"role": "user", "content": current_prompt})
                        current_prompt = msg["content"]
                    elif msg["role"] == "assistant":
                        if current_prompt:
                            conversation_history.append({"role": "user", "content": current_prompt})
                            current_prompt = ""
                        conversation_history.append({"role": "assistant", "content": msg["content"]})
                
                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is not set. Please configure it in your .env file.")
                
                claude_llm = LLM(
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                    model=model,
                    system_prompt="You are a helpful AI assistant. Provide clear, concise, and helpful responses.",
                )
                
                full_response = ""
                async for chunk in claude_llm.stream(
                    current_prompt,
                    conversation_history=conversation_history if conversation_history else None,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done', 'content': full_response})}\n\n"
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages
            if "401" in error_msg or "API key" in error_msg or "authentication" in error_msg.lower():
                error_msg = f"Authentication failed: {error_msg}. Please check your API key configuration in .env file."
            elif "404" in error_msg or "not found" in error_msg.lower():
                error_msg = f"Model not found: {error_msg}. Please check the model name."
            # Yield error as SSE message instead of raising exception
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Sandbox lifecycle endpoints
# ---------------------------------------------------------------------------


@app.post("/api/sandbox/create")
async def create_sandbox_endpoint():
    """Create a persistent Modal sandbox. Returns sandbox_id."""
    try:
        sandbox_id = await create_sandbox()
        return {"sandbox_id": sandbox_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Modal sandbox: {e}",
        )


@app.post("/api/sandbox/{sandbox_id}/terminate")
async def terminate_sandbox_endpoint(sandbox_id: str):
    """Terminate a persistent Modal sandbox."""
    found = await terminate_sandbox(sandbox_id)
    if not found:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return {"status": "terminated"}


# ---------------------------------------------------------------------------
# Run tests endpoint — execute code in a persistent sandbox
# ---------------------------------------------------------------------------


class RunTestsRequest(BaseModel):
    code: str
    challenge_id: str
    sandbox_id: str


class TestCaseResult(BaseModel):
    input: str
    expected: str
    actual: str | None = None
    passed: bool
    error: str | None = None


class RunTestsResponse(BaseModel):
    results: list[TestCaseResult]
    all_passed: bool
    passed_count: int
    total_count: int


@app.post("/api/run-tests")
async def run_tests(req: RunTestsRequest) -> RunTestsResponse:
    """Run code against a challenge's test suite in a persistent Modal sandbox."""
    challenge = get_challenge_by_id(req.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not challenge.test_suite:
        raise HTTPException(status_code=400, detail="Challenge has no test suite")

    test_dicts = [t.model_dump() for t in challenge.test_suite]
    try:
        raw_results = await run_function_tests_detailed(req.sandbox_id, req.code, test_dicts)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = [TestCaseResult(**r) for r in raw_results]
    passed_count = sum(1 for r in results if r.passed)
    return RunTestsResponse(
        results=results,
        all_passed=passed_count == len(results),
        passed_count=passed_count,
        total_count=len(results),
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.default_model}
