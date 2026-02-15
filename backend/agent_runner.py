"""
In-process agent runner: same logic as modal_agent/app.py but runs inside the backend.
Used when USE_INPROCESS_AGENT=true or when Modal spawn fails (e.g. local dev without Modal).
Supports simple loop (claude-direct, openai-cot) and Claude Agent SDK (claude-sdk).
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

from agents import get_agent_by_id
from challenges import get_challenge_by_id
from agent_turn import complete_agent_session, execute_prompt_turn
from llm import LLM
from evaluation.scoring import compute_accuracy_text
from sessions import get_session, add_turn, append_trace, Turn
from session_events import broadcast_session_event

logger = logging.getLogger(__name__)

# Optional debug log path for agent tool calls (prompts, scrape results, etc.)
_AGENT_TOOL_DEBUG_LOG = os.environ.get("LUCIDLY_DEBUG_LOG") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".cursor", "debug.log")
)


def _agent_tool_log(tool: str, *, args: dict[str, Any] | None = None, result_preview: str | None = None, result_full: str | None = None) -> None:
    """Log Claude SDK tool calls to the terminal and optionally to debug.log for inspection."""
    if args is not None:
        logger.info("[agent] %s args: %s", tool, json.dumps(args, ensure_ascii=False)[:2000])
    if result_preview is not None:
        logger.info("[agent] %s result: %s", tool, result_preview[:1500] if len(result_preview) > 1500 else result_preview)
    if result_full is not None:
        logger.info("[agent] %s result (full):\n%s", tool, result_full)
    try:
        with open(_AGENT_TOOL_DEBUG_LOG, "a") as f:
            entry = {
                "id": f"agent_tool_{tool}",
                "timestamp": time.time() * 1000,
                "tool": tool,
                "args": args,
                "result_preview": (result_preview or result_full or "")[:3000] if (result_preview or result_full) else None,
                "result_len": len(result_full) if result_full else None,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


MAX_TURNS = 10
ACCURACY_THRESHOLD = 0.95
COT_SYSTEM_PROMPT = (
    "You are a careful reasoner. Think step by step: analyze the requirement, "
    "plan the solution, then write the code. Put your reasoning first, then output "
    "the final code in a single markdown code block."
)


def _challenge_brief(challenge: Any) -> str:
    """Build challenge context matching what users see on the challenge page: title, description, reference, starter code."""
    title = getattr(challenge, "title", None) or (challenge.get("title") if isinstance(challenge, dict) else None) or "Challenge"
    description = getattr(challenge, "description", None) or (challenge.get("description") if isinstance(challenge, dict) else None) or ""
    embed_url = getattr(challenge, "embed_url", None) or (challenge.get("embed_url") if isinstance(challenge, dict) else None)
    html_url = getattr(challenge, "html_url", None) or (challenge.get("html_url") if isinstance(challenge, dict) else None)
    image_url = getattr(challenge, "image_url", None) or (challenge.get("image_url") if isinstance(challenge, dict) else None)
    starter_code = getattr(challenge, "starter_code", None) or (challenge.get("starter_code") if isinstance(challenge, dict) else None)
    parts = [f"Challenge: {title}\n\n{description}"]
    if html_url:
        parts.append("Reference: an HTML page is shown on the challenge page (recreate that design).")
    if embed_url:
        parts.append(f"Reference page (recreate this design): {embed_url}")
    if image_url:
        parts.append(f"Reference image or animation: {image_url}")
    if starter_code:
        parts.append(f"Starter code to extend or fix:\n```\n{starter_code}\n```")
    parts.append(
        "Your response will be executed and shown in a live preview. You must output runnable code in a single markdown code block. "
        "For UI challenges, output one complete HTML document (inline CSS/JS is fine). Do not respond with only 'DONE' or a summary—the first response must contain the code."
    )
    return "\n\n".join(parts)


async def _run_agent_loop_claude_sdk(
    session_id: str, challenge_id: str, agent_id: str
) -> None:
    """Run the Claude Agent SDK with a custom submit_prompt tool that calls our backend."""
    # #region agent log
    try:
        with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "id": "claude_sdk_entry",
                        "timestamp": time.time() * 1000,
                        "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                        "message": "claude_sdk entry",
                        "data": {"session_id": session_id[:8]},
                        "hypothesisId": "H1",
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    try:
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            ClaudeSDKClient,
            create_sdk_mcp_server,
            tool,
        )
    except ImportError as e:
        logger.error("claude-agent-sdk not installed: %s", e)
        # #region agent log
        try:
            with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                _f.write(
                    json.dumps(
                        {
                            "id": "claude_sdk_import_failed",
                            "timestamp": time.time() * 1000,
                            "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                            "message": "claude_sdk import failed",
                            "data": {"session_id": session_id[:8], "error": str(e)[:200]},
                            "hypothesisId": "H1",
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        complete_agent_session(session_id)
        return

    # #region agent log
    try:
        with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "id": "claude_sdk_import_ok",
                        "timestamp": time.time() * 1000,
                        "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                        "message": "claude_sdk import ok",
                        "data": {"session_id": session_id[:8]},
                        "hypothesisId": "H2",
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion

    import os
    from config import settings
    # Claude Agent SDK reads ANTHROPIC_API_KEY from env; without it receive_response() hangs
    if not (os.environ.get("ANTHROPIC_API_KEY") or getattr(settings, "anthropic_api_key", "")):
        # #region agent log
        try:
            with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                _f.write(
                    json.dumps(
                        {
                            "id": "claude_sdk_no_key",
                            "timestamp": time.time() * 1000,
                            "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                            "message": "claude_sdk requires ANTHROPIC_API_KEY",
                            "data": {"session_id": session_id[:8]},
                            "hypothesisId": "H5",
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        logger.error("Claude Agent SDK requires ANTHROPIC_API_KEY in .env (SDK uses Anthropic API, not OPENAI_API_KEY)")
        complete_agent_session(session_id)
        return
    if getattr(settings, "anthropic_api_key", ""):
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

    session = get_session(session_id)
    challenge = get_challenge_by_id(challenge_id)
    if not session or not challenge or session.status != "active":
        return

    t0 = time.time()
    _trace(session_id, "Starting Claude Agent SDK", t0)

    @tool(
        "submit_prompt",
        "Send a prompt to the code generation API. Returns the model response, generated code snippet, and accuracy (0-1). Use this to generate and refine code for the challenge.",
        {"prompt": str},
    )
    async def submit_prompt_tool(args: dict[str, Any]) -> dict[str, Any]:
        prompt_text = args.get("prompt") or ""
        _trace(session_id, "Requesting code from model", t0, prompt_len=len(prompt_text))
        _agent_tool_log("submit_prompt", args={"prompt": prompt_text})
        session_before = get_session(session_id)
        base_tokens = (session_before.total_tokens if session_before else 0)

        async def on_progress(estimated_response_tokens: int) -> None:
            total_est = base_tokens + (len(args.get("prompt") or "") // 4) + estimated_response_tokens
            await broadcast_session_event(
                session_id,
                {"type": "token_progress", "total_estimated_tokens": total_est},
            )

        data = await execute_prompt_turn(
            session_id,
            args["prompt"],
            on_progress=on_progress,
        )
        # Push final session so frontend gets real token count
        sess = get_session(session_id)
        if sess:
            await broadcast_session_event(
                session_id,
                {"type": "session_update", "session": sess.model_dump()},
            )
        acc = data.get("accuracy")
        if acc is not None:
            _trace(session_id, "Received code from model", t0, accuracy=round(float(acc), 2))
        snippet = (data.get("generated_code") or "")[:2000]
        response_text = data.get("response_text", "")[:1500]
        result_for_agent = f"Response: {response_text}\n\nGenerated code (excerpt):\n{snippet}\n\nAccuracy: {data.get('accuracy', 0):.2f}"
        _agent_tool_log(
            "submit_prompt",
            result_preview=f"accuracy={data.get('accuracy', 0):.2f} code_len={len(data.get('generated_code') or '')}",
            result_full=f"Response (excerpt):\n{response_text}\n\nGenerated code (excerpt):\n{snippet}",
        )
        return {
            "content": [
                {"type": "text", "text": result_for_agent}
            ]
        }

    embed_url = getattr(challenge, "embed_url", None) or (challenge.get("embed_url") if isinstance(challenge, dict) else None)
    html_url = getattr(challenge, "html_url", None) or (challenge.get("html_url") if isinstance(challenge, dict) else None)
    image_url = getattr(challenge, "image_url", None) or (challenge.get("image_url") if isinstance(challenge, dict) else None)
    has_reference = bool(embed_url or html_url or image_url)
    browserbase_configured = bool(
        getattr(settings, "browserbase_api_key", "") and getattr(settings, "browserbase_project_id", "")
    )

    @tool(
        "view_reference_page",
        "Open a URL in a browser and extract the landing page structure and content (title, nav, hero, sections, footer, styling notes). "
        "Use this when the challenge asks you to recreate a reference page (e.g. openai.com) so you can see what to build. "
        "Pass url to scrape, or leave empty to use the challenge's reference URL.",
        {"url": str},
    )
    async def view_reference_page_tool(args: dict[str, Any]) -> dict[str, Any]:
        url = (args.get("url") or "").strip() or embed_url or ""
        _agent_tool_log("view_reference_page", args={"url": url or "(empty, would use challenge embed_url)"})
        if not url:
            out = "No URL provided and this challenge has no reference URL. Use submit_prompt with a description of the page you want to build."
            _agent_tool_log("view_reference_page", result_preview=out)
            return {"content": [{"type": "text", "text": out}]}
        _trace(session_id, "Viewing reference page", t0, url=url[:60])
        from stagehand_scrape import scrape_landing_page
        model_api_key = getattr(settings, "openai_api_key", "") or getattr(settings, "anthropic_api_key", "")
        result = await scrape_landing_page(url, model_api_key=model_api_key or "dummy")
        if result.get("error"):
            text = f"Could not scrape {url}: {result['error']}"
        else:
            import json as _json
            extracted = result.get("extracted") or result
            text = f"Reference page: {url}\n\nExtracted structure and content:\n{_json.dumps(extracted, indent=2)}"
        text = text[:8000]
        _trace(session_id, "Reference page scraped", t0)
        _agent_tool_log("view_reference_page", result_preview=text[:500] + ("..." if len(text) > 500 else ""), result_full=text)
        return {"content": [{"type": "text", "text": text}]}

    tools_list: list[Any] = [submit_prompt_tool]
    allowed_tools_list = ["mcp__lucidly-challenge__submit_prompt"]
    if has_reference and browserbase_configured:
        tools_list.append(view_reference_page_tool)
        allowed_tools_list.append("mcp__lucidly-challenge__view_reference_page")

    custom_server = create_sdk_mcp_server(
        name="lucidly-challenge",
        version="1.0.0",
        tools=tools_list,
    )
    brief = _challenge_brief(challenge)
    _trace(session_id, "Task prepared for agent", t0)
    system_prompt_parts = [
        "You are completing a coding challenge. "
    ]
    if has_reference and browserbase_configured:
        system_prompt_parts.append(
            "When the challenge has a reference (landing page or design to recreate): use view_reference_page to extract the page structure, "
            "then use submit_prompt to generate matching HTML based on that structure. "
        )
    system_prompt_parts.append(
        "Use submit_prompt to send prompts to the code API. "
        "Your first tool call must produce code. "
        "Iterate until accuracy is 1.0 or you have tried enough, then reply with DONE.\n\n"
    )
    options = ClaudeAgentOptions(
        mcp_servers={"lucidly-challenge": custom_server},
        allowed_tools=allowed_tools_list,
        system_prompt="".join(system_prompt_parts) + brief,
        max_turns=MAX_TURNS,
    )

    # #region agent log
    try:
        with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "id": "claude_sdk_before_client",
                        "timestamp": time.time() * 1000,
                        "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                        "message": "claude_sdk before ClaudeSDKClient",
                        "data": {"session_id": session_id[:8]},
                        "hypothesisId": "H2",
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    try:
        async with ClaudeSDKClient(options=options) as client:
            # #region agent log
            try:
                with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                    _f.write(
                        json.dumps(
                            {
                                "id": "claude_sdk_before_query",
                                "timestamp": time.time() * 1000,
                                "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                                "message": "claude_sdk before client.query",
                                "data": {"session_id": session_id[:8]},
                                "hypothesisId": "H2,H4",
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            prompt = (
                "Complete this coding challenge. "
                + ("Use view_reference_page first, then submit_prompt to generate code. " if (has_reference and browserbase_configured) else "Use the submit_prompt tool to generate and refine code. ")
                + "Your first response must produce runnable code (HTML for UI challenges) in a markdown code block."
            )
            _trace(session_id, "Sending task to agent", t0)
            await client.query(prompt)
            _trace(session_id, "Agent reasoning…", t0)
            # #region agent log
            try:
                with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                    _f.write(
                        json.dumps(
                            {
                                "id": "claude_sdk_query_done",
                                "timestamp": time.time() * 1000,
                                "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                                "message": "claude_sdk client.query returned",
                                "data": {"session_id": session_id[:8]},
                                "hypothesisId": "H2",
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            async for _ in client.receive_response():
                pass
            _trace(session_id, "Agent finished", t0)
    except Exception as e:
        # #region agent log
        try:
            with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                _f.write(
                    json.dumps(
                        {
                            "id": "claude_sdk_exception",
                            "timestamp": time.time() * 1000,
                            "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                            "message": "claude_sdk exception",
                            "data": {"session_id": session_id[:8], "error": str(e)[:300]},
                            "hypothesisId": "H3",
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        logger.exception("Claude SDK run failed: %s", e)
    finally:
        # #region agent log
        try:
            with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
                _f.write(
                    json.dumps(
                        {
                            "id": "claude_sdk_finally",
                            "timestamp": time.time() * 1000,
                            "location": "agent_runner.py:_run_agent_loop_claude_sdk",
                            "message": "claude_sdk finally",
                            "data": {"session_id": session_id[:8]},
                            "hypothesisId": "H3",
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        complete_agent_session(session_id)
        logger.info("Claude SDK agent run finished: session_id=%s", session_id)


def _trace(session_id: str, step: str, t0: float, **kwargs: Any) -> None:
    elapsed_ms = int((time.time() - t0) * 1000)
    extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info("[agent_trace] session_id=%s %s (+%dms) %s", session_id[:8], step, elapsed_ms, extra or "")
    session = get_session(session_id)
    if session and session.username.startswith("agent:"):
        append_trace(session_id, step, elapsed_ms, **kwargs)
    # #region agent log
    try:
        with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "id": f"trace_{step.replace(' ', '_')[:30]}",
                        "timestamp": time.time() * 1000,
                        "location": "agent_runner.py:_trace",
                        "message": f"agent_trace {step}",
                        "data": {"session_id": session_id[:8], "elapsed_ms": elapsed_ms, **kwargs},
                        "hypothesisId": "H1",
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


def _debug_log(message: str, data: dict, hypothesis_id: str = "H1") -> None:
    # #region agent log
    try:
        with open("/Users/helenazhou/Dev/lucidly/.cursor/debug.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "id": f"agent_{message.replace(' ', '_')[:40]}",
                        "timestamp": time.time() * 1000,
                        "location": "agent_runner.py:run_agent_loop",
                        "message": message,
                        "data": data,
                        "hypothesisId": hypothesis_id,
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


async def run_agent_loop(session_id: str, challenge_id: str, agent_id: str) -> None:
    """
    Run the agent loop in-process: load challenge, submit prompts via LLM, record turns, complete.
    Mirrors modal_agent/app.py so behavior is identical.
    """
    # #region agent log
    _debug_log(
        "run_agent_loop entered",
        {"session_id": session_id[:8], "challenge_id": challenge_id, "agent_id": agent_id},
        "H1,H2",
    )
    # #endregion

    t0 = time.time()
    _trace(session_id, "Starting run", t0, challenge_id=challenge_id, agent_id=agent_id)

    session = get_session(session_id)
    if session is None:
        # #region agent log
        _debug_log("run_agent_loop early exit", {"reason": "session_not_found"}, "H3")
        # #endregion
        logger.error("Agent run: session %s not found", session_id)
        return
    if session.status != "active":
        # #region agent log
        _debug_log("run_agent_loop early exit", {"reason": "session_not_active", "status": session.status}, "H3")
        # #endregion
        logger.warning("Agent run: session %s not active", session_id)
        return

    agent = get_agent_by_id(agent_id)
    challenge = get_challenge_by_id(challenge_id)
    if not agent or not challenge:
        # #region agent log
        _debug_log("run_agent_loop early exit", {"reason": "agent_or_challenge_not_found"}, "H3")
        # #endregion
        logger.error("Agent run: agent or challenge not found")
        return

    if agent_id == "claude-sdk":
        # #region agent log
        _debug_log("run_agent_loop branch", {"branch": "claude-sdk"}, "H3,H4")
        # #endregion
        _trace(session_id, "Starting Claude Agent SDK", t0)
        await _run_agent_loop_claude_sdk(session_id, challenge_id, agent_id)
        return
    # #region agent log
    _debug_log("run_agent_loop branch", {"branch": "simple_loop"}, "H3,H4")
    # #endregion

    from config import settings
    model_used = agent.model or settings.default_model
    _trace(session_id, "Preparing task", t0)
    brief = _challenge_brief(challenge)
    _trace(session_id, "Initializing model", t0)

    def first_turn_prompt(aid: str) -> str:
        if aid == "openai-cot":
            return (
                brief
                + "\n\nThink step by step. First analyze the requirement, then plan the solution, then write the code. "
                "Put your reasoning first, then output the final code in a single markdown code block."
            )
        return (
            brief
            + "\n\nGenerate complete, runnable code that fulfills this challenge. Output the code in a single markdown code block."
        )

    llm = LLM(model=model_used)
    turn_count = 0

    try:
        while turn_count < MAX_TURNS:
            turn_count += 1
            if turn_count == 1:
                prompt = first_turn_prompt(agent_id)
                system_prompt = COT_SYSTEM_PROMPT if agent_id == "openai-cot" else None
            else:
                last_turn = session.turns[-1] if session.turns else None
                last_had_code = last_turn and (last_turn.generated_code or "").strip()
                if not last_had_code:
                    prompt = (
                        "Your previous response did not include runnable code in a markdown code block. "
                        "Please output a complete HTML document now in a single markdown code block (```html on one line, then your code, then ```). "
                        "No explanations—just the code block."
                    )
                else:
                    prompt = (
                        "Review the previous response and improve the code if accuracy was not 100%. "
                        "Otherwise respond with: DONE"
                    )
                system_prompt = None

            history: list[dict] = []
            for t in session.turns:
                history.append({"role": "user", "content": t.prompt_text})
                history.append({"role": "assistant", "content": t.response_text})

            # Expose current prompt only for first turn (challenge brief); hide internal follow-ups
            s = get_session(session_id)
            if s and turn_count == 1:
                s.current_prompt = prompt
            elif s and turn_count > 1:
                s.current_prompt = None

            _trace(session_id, "Sending task to model", t0, prompt_len=len(prompt))
            max_tok = getattr(settings, "max_completion_tokens_agent", 4096)
            base_tokens = session.total_tokens
            full_response = ""
            async for chunk in llm.stream(
                prompt,
                conversation_history=history if history else None,
                system_prompt=system_prompt,
                max_tokens=max_tok,
            ):
                full_response += chunk
                est = len(full_response) // 4
                total_est = base_tokens + (len(prompt) // 4) + est
                await broadcast_session_event(
                    session_id,
                    {"type": "token_progress", "total_estimated_tokens": total_est},
                )

            generated_code = LLM.extract_code_blocks(full_response)
            est_prompt_tokens = len(prompt.split()) * 2
            est_response_tokens = len(full_response.split()) * 2
            _trace(session_id, "Model responded", t0, response_tokens=est_response_tokens)

            accuracy = 0.0
            if challenge.target_code:
                accuracy = compute_accuracy_text(generated_code, challenge.target_code)

            turn = Turn(
                turn_number=len(session.turns) + 1,
                prompt_text=prompt,
                prompt_tokens=est_prompt_tokens,
                response_text=full_response,
                response_tokens=est_response_tokens,
                generated_code=generated_code,
                accuracy_at_turn=accuracy,
                timestamp=time.time(),
            )
            add_turn(session_id, turn)
            sess = get_session(session_id)
            if sess:
                await broadcast_session_event(
                    session_id,
                    {"type": "session_update", "session": sess.model_dump()},
                )
            _trace(session_id, "Saved response", t0)
            session = get_session(session_id)
            if session:
                session.current_prompt = None
            if not session:
                break

            if agent_id == "claude-direct":
                break
            if accuracy >= ACCURACY_THRESHOLD:
                break
            if "DONE" in (full_response or "").upper():
                break

        complete_agent_session(session_id)
        _trace(session_id, "Done", t0, total_turns=turn_count)
        logger.info("Agent run completed: session_id=%s turns=%s", session_id, turn_count)
    except Exception as e:
        logger.exception("Agent run failed: session_id=%s %s", session_id, e)
    finally:
        s = get_session(session_id)
        if s:
            s.current_prompt = None
