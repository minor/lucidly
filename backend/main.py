"""Lucidly backend — FastAPI application."""

import asyncio
import json
import logging
import re
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Ensure logger outputs to console
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from config import settings
from llm import LLM
from challenges import get_all_challenges, get_challenge_by_id
from agents import get_all_agents, get_agent_by_id
from agent_runner import run_agent_loop
from agent_turn import execute_prompt_turn
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
from session_events import (
    broadcast_session_event,
    subscribe_session_events,
    unsubscribe_session_events,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Lucidly", version="0.1.0")


@app.on_event("startup")
def _configure_agent_trace_logging():
    """Run in the worker process so [agent_trace] appears in the console and in the debug log."""
    import sys
    _agent_log = logging.getLogger("agent_runner")
    _agent_log.setLevel(logging.INFO)
    if not _agent_log.handlers:
        _h = logging.StreamHandler(sys.stderr)
        _h.setLevel(logging.INFO)
        _h.setFormatter(logging.Formatter("%(message)s"))
        _h.terminator = "\n"
        _agent_log.addHandler(_h)
        _agent_log.propagate = False


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


class CalculateScoreRequest(BaseModel):
    challenge_id: str
    accuracy: float
    elapsed_sec: float
    total_tokens: int
    total_turns: int
    difficulty: str = "medium"
    model: str = "unknown"
    # Optional fields for persistence
    username: str | None = None
    messages: list[dict] | None = None
    total_cost: float | None = 0.0

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


@app.get("/api/challenges/{challenge_id}/html")
async def get_challenge_html(challenge_id: str):
    """Serve the HTML file content for a challenge's html_url."""
    challenge = get_challenge_by_id(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    if not challenge.html_url:
        raise HTTPException(status_code=404, detail="Challenge has no html_url")
    
    from pathlib import Path
    # html_url is a path like "backend/challenge_code/openai-landing.html"
    # We need to resolve it relative to the project root
    project_root = Path(__file__).parent.parent
    html_path = project_root / challenge.html_url
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"HTML file not found: {challenge.html_url}")
    
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return Response(content=html_content, media_type="text/html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read HTML file: {str(e)}")


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


@app.get("/api/sessions/{session_id}/events")
async def session_events_stream(session_id: str):
    """
    Server-Sent Events stream for agent run sessions.
    Pushes token_progress (estimated tokens during LLM stream) and session_update (full session when turn completes).
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = subscribe_session_events(session_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # SSE format: "data: {json}\n\n"
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe_session_events(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

    data = await execute_prompt_turn(
        session_id,
        req.prompt,
        model=req.model,
        system_prompt=req.system_prompt,
    )
    return PromptResponse(
        turn_number=data["turn_number"],
        response_text=data["response_text"],
        generated_code=data["generated_code"],
        prompt_tokens=data["prompt_tokens"],
        response_tokens=data["response_tokens"],
        accuracy=data["accuracy"],
        test_results=None,
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
        difficulty=challenge.difficulty or "medium",
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
async def leaderboard(limit: int = 50, category: str | None = None, challenge_id: str | None = None):
    """Fetch leaderboard entries from Supabase."""
    from database import get_leaderboard as get_db_leaderboard
    
    # Fetch from Supabase
    entries = await get_db_leaderboard(challenge_id=challenge_id, limit=limit)
    
    # Filter by category if provided (since DB currently filters by challenge_id only)
    if category and category != "all":
        entries = [e for e in entries if e.get("category") == category]
        
    return entries


# ---------------------------------------------------------------------------
# Score calculation endpoint (for direct score calculation without session)
# ---------------------------------------------------------------------------


@app.post("/api/calculate-score")
async def calculate_score(req: CalculateScoreRequest):
    """Calculate composite score from challenge stats and persist to DB."""
    scores = compute_composite_score(
        accuracy=req.accuracy,
        elapsed_sec=req.elapsed_sec,
        total_tokens=req.total_tokens,
        total_turns=req.total_turns,
        difficulty=req.difficulty,
    )
    
    
    # Persist to Supabase if credentials exist and username/messages are provided
    if req.username and req.messages:
        try:
            from database import save_challenge_session
            from challenges import get_challenge_by_id
            
            challenge = get_challenge_by_id(req.challenge_id)
            if challenge:
                 db_session_id = await save_challenge_session(
                    challenge_id=req.challenge_id,
                    title=challenge.title,
                    category=challenge.category,
                    difficulty=req.difficulty,
                    model=req.model, 
                    username=req.username,
                    accuracy=req.accuracy,
                    time_seconds=req.elapsed_sec,
                    total_tokens=req.total_tokens,
                    total_turns=req.total_turns,
                    total_cost=req.total_cost or 0.0,
                    composite_score=scores["composite_score"],
                    accuracy_score=scores["accuracy_score"],
                    speed_score=scores["speed_score"],
                    token_score=scores["token_score"],
                    turn_score=scores["turn_score"],
                    messages=req.messages
                 )
                 if db_session_id:
                     scores["db_session_id"] = db_session_id
        except Exception as e:
            logger.error(f"Failed to save score: {e}")
        
    return scores


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
    model_used = agent.model or settings.default_model
    session = create_session(req.challenge_id, model_used, username)
    modal_spawned = False


    if not settings.use_inprocess_agent:
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
            modal_spawned = True
        except Exception as e:
            logger.warning("Modal spawn failed, falling back to in-process agent: %s", e)
            asyncio.create_task(
                run_agent_loop(session.id, req.challenge_id, req.agent_id)
            )
    else:
        asyncio.create_task(
            run_agent_loop(session.id, req.challenge_id, req.agent_id)
        )

    return {
        "session_id": session.id,
        "challenge_id": req.challenge_id,
        "agent_id": req.agent_id,
        "modal_spawned": modal_spawned,
    }


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
                # GPT-5 Mini and Nano require temperature=1
                temperature = 1.0 if model in ["gpt-5-mini", "gpt-5-nano"] else None
                
                async for chunk in llm_instance.stream(
                    prompt_text,
                    conversation_history=history if history else None,
                    temperature=temperature,
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
    
    # Determine if we should use Anthropic API directly based on model name
    # Default to OpenAI if model is not explicitly Claude
    is_claude_model = req.model is not None and req.model.startswith("claude")
    use_anthropic = bool(settings.anthropic_api_key) and is_claude_model
    
    # Validate that we have at least one API key configured
    if not use_anthropic and not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="No API key configured. Please set either ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
        )
    
    # Use correct Anthropic model names
    # Valid models: claude-3-5-sonnet-20240620, claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
    # Map short names to full IDs for Anthropic API
    MODEL_MAPPING = {
        "claude-opus-4-6": "claude-opus-4-6",  # Assuming standard date suffix or similar
        "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    }
    
    raw_model = req.model or settings.default_model
    model = MODEL_MAPPING.get(raw_model, raw_model)
    
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
                        "max_tokens": settings.max_tokens,
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
                        input_tokens = 0
                        output_tokens = 0
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    event_type = data.get("type")
                                    if event_type == "message_start":
                                        usage = data.get("message", {}).get("usage", {})
                                        input_tokens = usage.get("input_tokens", 0)
                                        # Send input tokens immediately
                                        yield f"data: {json.dumps({'type': 'usage', 'input_tokens': input_tokens})}\n\n"
                                    elif event_type == "content_block_delta":
                                        chunk = data.get("delta", {}).get("text", "")
                                        if chunk:
                                            full_response += chunk
                                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                                    elif event_type == "message_delta":
                                        usage = data.get("usage", {})
                                        output_tokens = usage.get("output_tokens", 0)
                                    elif event_type == "message_stop":
                                        break
                                except json.JSONDecodeError:
                                    continue
                        
                        # Dynamic cost calculation
                        from config import MODEL_PRICING
                        model_name = req.model or "claude-3-opus"
                        pricing = MODEL_PRICING.get(model_name)
                        
                        # Fallback logic if exact match fails
                        if not pricing:
                            for key, p in MODEL_PRICING.items():
                                if model_name.startswith(key):
                                    pricing = p
                                    break
                        
                        # Default to Opus if still not found
                        if not pricing:
                            pricing = {"input": 15.0, "output": 75.0}

                        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
                        
                        yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost': cost})}\n\n"
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
                # GPT-5 Mini and Nano require temperature=1
                temperature = 1.0 if model in ["gpt-5-mini", "gpt-5-nano"] else None
                
                async for chunk in claude_llm.stream(
                    current_prompt,
                    conversation_history=conversation_history if conversation_history else None,
                    temperature=temperature,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Estimate tokens (approx 1.3 tokens per word is standard, but keeping consistent with session_ws * 2 if preferred, 
                # though * 1.3 is closer to reality for English. Let's use a simple heuristic.)
                # session_ws uses * 2. Let's use * 1.5 as a middle ground or stick to simple word count.
                # Actually, main.py session_ws uses len(split()) * 2.
                est_input_tokens = len(current_prompt.split()) * 2
                est_output_tokens = len(full_response.split()) * 2
                
                # Emit usage event for input tokens so frontend updates headers
                yield f"data: {json.dumps({'type': 'usage', 'input_tokens': est_input_tokens})}\n\n"

                # Dynamic cost calculation
                from config import MODEL_PRICING
                pricing = MODEL_PRICING.get(model)
                if not pricing:
                     for key, p in MODEL_PRICING.items():
                        if model.startswith(key):
                            pricing = p
                            break
                if not pricing:
                    pricing = {"input": 0.0, "output": 0.0}

                cost = (est_input_tokens * pricing["input"] + est_output_tokens * pricing["output"]) / 1_000_000
                
                yield f"data: {json.dumps({'type': 'done', 'content': full_response, 'input_tokens': est_input_tokens, 'output_tokens': est_output_tokens, 'cost': cost})}\n\n"
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


class RunCodeRequest(BaseModel):
    sandbox_id: str
    code: str


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


class EvaluateUIRequest(BaseModel):
    challenge_id: str
    generated_html: str


class EvaluateUIResponse(BaseModel):
    score: float  # 0-100
    similarity_score: float  # 0-1
    detailed_feedback: str | None = None

@app.post("/api/evaluate-ui")
async def evaluate_ui(req: EvaluateUIRequest, request: Request) -> EvaluateUIResponse:
    """Evaluate UI challenge by comparing generated HTML with challenge reference HTML code."""
    print(f"\n{'='*60}")
    print(f"[UI Evaluation] ===== EVALUATION REQUEST RECEIVED =====")
    print(f"[UI Evaluation] Challenge ID: {req.challenge_id}")
    print(f"[UI Evaluation] Generated HTML length: {len(req.generated_html)} characters")
    print(f"{'='*60}\n")
    
    logger.info(f"[UI Evaluation] Received request for challenge: {req.challenge_id}")
    logger.info(f"[UI Evaluation] Generated HTML length: {len(req.generated_html)} characters")
    
    challenge = get_challenge_by_id(req.challenge_id)
    if challenge is None:
        logger.error(f"[UI Evaluation] Challenge not found: {req.challenge_id}")
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    if challenge.category != "ui":
        logger.error(f"[UI Evaluation] Challenge is not UI category: {challenge.category}")
        raise HTTPException(status_code=400, detail="Challenge is not a UI challenge")
    
    if not challenge.html_url:
        logger.error("[UI Evaluation] Challenge has no html_url")
        raise HTTPException(
            status_code=400,
            detail="Challenge must have html_url for UI evaluation"
        )
    
    logger.info(f"[UI Evaluation] Challenge found: {challenge.title}")
    logger.info(f"[UI Evaluation] Using HTML code comparison method")
    
    try:
        # Load reference HTML from challenge's html_url
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        html_path = project_root / challenge.html_url
        
        if not html_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Reference HTML file not found: {challenge.html_url}"
            )
        
        with open(html_path, "r", encoding="utf-8") as f:
            reference_html = f.read()
        
        logger.info(f"[UI Evaluation] Reference HTML loaded ({len(reference_html)} characters)")
        logger.info(f"[UI Evaluation] Generated HTML length: {len(req.generated_html)} characters")
        
        # Use OpenAI to compare the HTML codes
        from llm import LLM
        
        evaluation_prompt = f"""You are a kind and generous scoring expert when it comes to evaluating HTML code similarity. Compare the reference HTML code with the generated HTML code and provide a similarity score between 0-100.

Consider the following aspects when evaluating:
1. **Structure and Layout**: HTML structure, element hierarchy, semantic elements
2. **Styling**: CSS styles, colors, fonts, spacing, layout properties
3. **Content**: Text content, images, links, and other media
4. **Overall Visual Match**: How closely the generated code would render compared to the reference

**Reference HTML Code:**
```html
{reference_html}
```

**Generated HTML Code:**
```html
{req.generated_html}
```

**Challenge Description:**
{challenge.description}

Please evaluate the similarity and provide your response in the following JSON format:
{{
    "score": <number between 0-100>,
    "reasoning": "<detailed explanation of the similarity score, including what matches well and what differs>"
}}

Be thorough in your evaluation. A score of 100 means the codes are essentially identical in structure, styling, content, and functionality. Lower scores indicate increasing differences."""
        
        # Use OpenAI model for evaluation
        llm = LLM(
            model=settings.default_model,
            system_prompt="You are an expert HTML/CSS/JavaScript evaluator. Provide accurate and detailed similarity assessments.",
            temperature=0.3,  # Lower temperature for more consistent evaluation
        )
        
        logger.info("[UI Evaluation] Calling OpenAI model for HTML comparison...")
        print(f"[UI Evaluation] Calling OpenAI model: {settings.default_model}")
        print(f"[UI Evaluation] Prompt length: {len(evaluation_prompt)} characters")
        
        response = await llm.generate(evaluation_prompt)
        response_text = response.response_text.strip()
        
        # Log the full response for debugging
        print(f"[UI Evaluation] OpenAI API Response received:")
        print(f"[UI Evaluation] Response length: {len(response_text)} characters")
        print(f"[UI Evaluation] Full response text:\n{response_text}")
        logger.info(f"[UI Evaluation] OpenAI API Response received ({len(response_text)} chars)")
        logger.info(f"[UI Evaluation] Full response: {response_text}")
        
        # Extract JSON from response (might be wrapped in markdown code block)
        json_match = None
        # Try to find JSON in code blocks first
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            print(f"[UI Evaluation] Found JSON in code block")
        else:
            # Try to find JSON object directly
            json_pattern = r'\{.*?\}'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print(f"[UI Evaluation] Found JSON object directly")
            else:
                # Fallback: try to parse the whole response
                json_str = response_text
                print(f"[UI Evaluation] Using entire response as JSON")
        
        print(f"[UI Evaluation] Extracted JSON string length: {len(json_str)} characters")
        print(f"[UI Evaluation] Extracted JSON (first 500 chars): {json_str[:500]}")
        
        try:
            evaluation_result = json.loads(json_str)
            score = float(evaluation_result.get("score", 0))
            reasoning = evaluation_result.get("reasoning", "No reasoning provided")
            
            # Clamp score to 0-100 range
            score = max(0, min(100, score))
            similarity_score = score / 100.0  # Convert to 0-1 range
            
            print(f"[UI Evaluation] ========================================")
            print(f"[UI Evaluation] Evaluation Result:")
            print(f"[UI Evaluation] Score: {score:.1f}/100")
            print(f"[UI Evaluation] Similarity: {similarity_score:.4f}")
            print(f"[UI Evaluation] Reasoning: {reasoning}")
            print(f"[UI Evaluation] ========================================")
            
            logger.info(f"[UI Evaluation] Comparison completed. Score: {score:.1f}/100")
            logger.info(f"[UI Evaluation] Similarity: {similarity_score:.4f}")
            logger.info(f"[UI Evaluation] Full reasoning: {reasoning}")
            
            return EvaluateUIResponse(
                score=score,
                similarity_score=similarity_score,
                detailed_feedback=reasoning,
            )
        except json.JSONDecodeError as e:
            print(f"[UI Evaluation] ERROR: Failed to parse JSON from response")
            print(f"[UI Evaluation] JSONDecodeError: {e}")
            print(f"[UI Evaluation] Response text (first 1000 chars): {response_text[:1000]}")
            logger.error(f"[UI Evaluation] Failed to parse JSON from response: {e}")
            logger.error(f"[UI Evaluation] Response text: {response_text[:1000]}")
            # Fallback: try to extract score from text
            score_match = re.search(r'(\d+(?:\.\d+)?)', response_text)
            if score_match:
                score = float(score_match.group(1))
                score = max(0, min(100, score))
                print(f"[UI Evaluation] Fallback: Extracted score from text: {score}")
                return EvaluateUIResponse(
                    score=score,
                    similarity_score=score / 100.0,
                    detailed_feedback=f"Could not parse full response. Extracted score: {score}. Raw response: {response_text[:500]}",
                )
            raise HTTPException(
                status_code=500,
                detail="Failed to parse evaluation response from OpenAI"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[UI Evaluation] ERROR: Exception occurred: {e}")
        print(f"[UI Evaluation] Exception type: {type(e).__name__}")
        import traceback
        print(f"[UI Evaluation] Traceback:\n{traceback.format_exc()}")
        logger.error(f"UI evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate UI: {str(e)}"
        )


@app.post("/api/run-code")
async def run_code(req: RunCodeRequest):
    """Run arbitrary code in a sandbox (for data challenges)."""
    try:
        from sandbox import run_code_in_sandbox
        result = await run_code_in_sandbox(req.sandbox_id, req.code)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Prompt feedback endpoint — AI-powered analysis of user prompts
# ---------------------------------------------------------------------------


class PromptFeedbackRequest(BaseModel):
    messages: list[ChatMessage]
    challenge_id: str
    challenge_description: str = ""
    challenge_category: str = ""
    challenge_difficulty: str = ""
    reference_html: str = ""  # Original HTML the user was trying to recreate
    accuracy: float = 0.0
    total_turns: int = 0
    total_tokens: int = 0
    elapsed_sec: float = 0.0
    db_session_id: str | None = None  # Supabase session ID for persisting feedback


PROMPT_FEEDBACK_SYSTEM_PROMPT = (
    "You are a concise, supportive prompt engineering coach. You give direct, non-redundant "
    "feedback. Never repeat the same point across sections. Be warm but respect the reader's "
    "intelligence — don't over-explain obvious things. Quote the user's actual prompts when relevant."
)


def _build_feedback_analysis_prompt(req: PromptFeedbackRequest) -> str:
    """Build the analysis prompt that evaluates the user's prompting strategy."""
    user_prompts = []
    for i, msg in enumerate(req.messages):
        if msg.role == "user":
            user_prompts.append(f"**Prompt {len(user_prompts) + 1}:** {msg.content}")

    conversation_text = "\n\n".join(
        f"**{msg.role.upper()}:** {msg.content[:1500]}{'...' if len(msg.content) > 1500 else ''}"
        for msg in req.messages
    )

    # Build reference HTML context section if available
    reference_section = ""
    convergence_section = ""
    if req.reference_html:
        truncated_html = req.reference_html[:3000]
        if len(req.reference_html) > 3000:
            truncated_html += "\n... (truncated)"
        reference_section = f"""
## Reference Target
The user was shown this HTML and asked to recreate it by prompting an AI:

```html
{truncated_html}
```
"""
        convergence_section = """
### Convergence
Did the prompts move the output closer to the reference over successive turns? List the key elements from the reference that the user described well, and list which ones they missed (just name them — no need to explain what they are). One sentence on the overall trajectory.
"""

    return f"""Analyze this prompt engineering session. Be encouraging but concise — say each thing once.

## Challenge Context
- **Category:** {req.challenge_category}
- **Difficulty:** {req.challenge_difficulty}
- **Description:** {req.challenge_description}
{reference_section}
## Stats
- **Accuracy:** {req.accuracy:.0%} · **Turns:** {req.total_turns} · **Tokens:** {req.total_tokens:,} · **Time:** {req.elapsed_sec:.0f}s

## User's Prompts
{chr(10).join(user_prompts)}

## Full Conversation
{conversation_text}

---

Write feedback in **markdown**. Follow these rules strictly:
- **No letter grades or numeric scores.** Do not grade the user.
- **Say each point exactly once.** If you mention something in the summary, don't repeat it in a later section.
- **Don't over-explain obvious UI elements.** If listing missing features, just name them — the user knows what a navbar is.
- **Be direct.** One point per bullet. No filler phrases like "which matches a tiny slice of" or "it's worth noting that."

Use these sections and ONLY these sections:

### Summary
2-3 sentences. What went well and what the main opportunity is. This is the only place for high-level observations — later sections go deeper, not wider.
{convergence_section}
### Strengths & Gaps
One unified section. Bullet the specific things the user did effectively (quote their prompts), then bullet what was missing or vague. Don't re-list anything from the summary — go into new detail here.

### Sharpest Improvement
The single highest-leverage change that would have made the biggest difference in this session. Be specific — reference an actual prompt and show what a better version would look like. Keep it to 2-3 sentences.

### Prompt Templates to Try
End with 2-3 **concrete prompt formats/wrappers** the user can copy-paste and adapt for future challenges. These should be reusable structures, not advice. Format them as fenced code blocks. For example:

```
Build [component] with: layout: [describe], colors: [list], typography: [font/sizes], content: [exact text], interactions: [list behaviors]
```

Each template should address a gap you identified in this session.

Keep it short. The whole response should be readable in under 60 seconds."""


@app.post("/api/prompt-feedback")
async def prompt_feedback(req: PromptFeedbackRequest):
    """
    Stream AI-powered feedback on the user's prompt engineering.
    Uses SSE to stream the analysis as it's generated.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages to analyze")

    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user prompts to analyze")

    analysis_prompt = _build_feedback_analysis_prompt(req)

    db_session_id = req.db_session_id

    async def generate():
        try:
            feedback_llm = LLM(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                model=settings.default_model,
                system_prompt=PROMPT_FEEDBACK_SYSTEM_PROMPT,
            )

            full_response = ""
            async for chunk in feedback_llm.stream(
                analysis_prompt,
                temperature=0.4,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'content': full_response})}\n\n"

            # Persist feedback to Supabase if we have a session ID
            if db_session_id and full_response:
                try:
                    from database import save_prompt_feedback
                    await save_prompt_feedback(db_session_id, full_response)
                except Exception as e:
                    logger.error(f"Failed to persist prompt feedback: {e}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Prompt feedback failed: {error_msg}")
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