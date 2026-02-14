"""
In-process agent runner: same logic as modal_agent/app.py but runs inside the backend.
Used when USE_INPROCESS_AGENT=true or when Modal spawn fails (e.g. local dev without Modal).
Supports simple loop (claude-direct, openai-cot), Claude Agent SDK (claude-sdk), and OpenAI Assistant (openai-assistant).
"""

import asyncio
import logging
import time
from typing import Any

from agents import get_agent_by_id
from challenges import get_challenge_by_id
from agent_turn import complete_agent_session, execute_prompt_turn
from llm import LLM
from evaluation.scoring import compute_accuracy_text
from sessions import get_session, add_turn, Turn

logger = logging.getLogger(__name__)

MAX_TURNS = 10
ACCURACY_THRESHOLD = 0.95
COT_SYSTEM_PROMPT = (
    "You are a careful reasoner. Think step by step: analyze the requirement, "
    "plan the solution, then write the code. Put your reasoning first, then output "
    "the final code in a single markdown code block."
)


def _challenge_brief(challenge: Any) -> str:
    """Build full challenge context for the agent: title, description, reference URLs, output format."""
    title = getattr(challenge, "title", None) or (challenge.get("title") if isinstance(challenge, dict) else None) or "Challenge"
    description = getattr(challenge, "description", None) or (challenge.get("description") if isinstance(challenge, dict) else None) or ""
    embed_url = getattr(challenge, "embed_url", None) or (challenge.get("embed_url") if isinstance(challenge, dict) else None)
    image_url = getattr(challenge, "image_url", None) or (challenge.get("image_url") if isinstance(challenge, dict) else None)
    starter_code = getattr(challenge, "starter_code", None) or (challenge.get("starter_code") if isinstance(challenge, dict) else None)
    parts = [f"Challenge: {title}\n\n{description}"]
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
    try:
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            ClaudeSDKClient,
            create_sdk_mcp_server,
            tool,
        )
    except ImportError as e:
        logger.error("claude-agent-sdk not installed: %s", e)
        complete_agent_session(session_id)
        return

    session = get_session(session_id)
    challenge = get_challenge_by_id(challenge_id)
    if not session or not challenge or session.status != "active":
        return

    @tool(
        "submit_prompt",
        "Send a prompt to the code generation API. Returns the model response, generated code snippet, and accuracy (0-1). Use this to generate and refine code for the challenge.",
        {"prompt": str},
    )
    async def submit_prompt_tool(args: dict[str, Any]) -> dict[str, Any]:
        data = await execute_prompt_turn(session_id, args["prompt"])
        snippet = (data.get("generated_code") or "")[:2000]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Response: {data.get('response_text', '')[:1500]}\n\nGenerated code (excerpt):\n{snippet}\n\nAccuracy: {data.get('accuracy', 0):.2f}",
                }
            ]
        }

    custom_server = create_sdk_mcp_server(
        name="lucidly-challenge",
        version="1.0.0",
        tools=[submit_prompt_tool],
    )
    brief = _challenge_brief(challenge)
    options = ClaudeAgentOptions(
        mcp_servers={"lucidly-challenge": custom_server},
        allowed_tools=["mcp__lucidly-challenge__submit_prompt"],
        system_prompt=(
            "You are completing a coding challenge. Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and an accuracy score. "
            "Your first tool call must ask for code that fulfills the challenge (the response will be run in a preview). "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE.\n\n"
            f"{brief}"
        ),
        max_turns=MAX_TURNS,
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            prompt = "Complete this coding challenge. Use the submit_prompt tool to generate and refine code. Your first response must request runnable code (HTML for UI challenges) in a markdown code block."
            await client.query(prompt)
            async for _ in client.receive_response():
                pass
    except Exception as e:
        logger.exception("Claude SDK run failed: %s", e)
    finally:
        complete_agent_session(session_id)
        logger.info("Claude SDK agent run finished: session_id=%s", session_id)


async def _run_agent_loop_openai_assistant(
    session_id: str, challenge_id: str, agent_id: str
) -> None:
    """Run the OpenAI Assistants API with a submit_prompt function tool."""
    from openai import AsyncOpenAI
    from config import settings

    session = get_session(session_id)
    challenge = get_challenge_by_id(challenge_id)
    if not session or not challenge or session.status != "active":
        return
    agent = get_agent_by_id(agent_id)
    if not agent:
        return

    brief = _challenge_brief(challenge)
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    assistant = await client.beta.assistants.create(
        name="Lucidly Challenge Agent",
        instructions=(
            "You are completing a coding challenge. Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and accuracy. Your first tool call must request runnable code. "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE.\n\n"
            f"{brief}"
        ),
        model=agent.model or settings.default_model,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "submit_prompt",
                    "description": "Send a prompt to the code generation API. Returns response, generated code excerpt, and accuracy (0-1).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "The prompt to send to the code API",
                            }
                        },
                        "required": ["prompt"],
                    },
                },
            }
        ],
    )

    thread = await client.beta.threads.create()
    await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Complete this coding challenge using the submit_prompt tool. Challenge: {title}\n\n{description}",
    )

    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )
    max_steps = 20
    step = 0
    try:
        while step < max_steps:
            step += 1
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run.status == "completed":
                break
            if run.status == "failed":
                logger.warning("OpenAI Assistant run failed: %s", run.last_error)
                break
            if run.status == "requires_action":
                import json
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                outputs = []
                for tc in tool_calls:
                    name = getattr(tc.function, "name", "") or ""
                    if name != "submit_prompt":
                        outputs.append({"tool_call_id": tc.id, "output": "Unknown tool"})
                        continue
                    args = json.loads(getattr(tc.function, "arguments", None) or "{}")
                    prompt = args.get("prompt", "")
                    data = await execute_prompt_turn(session_id, prompt)
                    snippet = (data.get("generated_code") or "")[:1500]
                    output = f"Response: {(data.get('response_text') or '')[:1000]}\n\nGenerated code (excerpt):\n{snippet}\n\nAccuracy: {data.get('accuracy', 0):.2f}"
                    outputs.append({"tool_call_id": tc.id, "output": output})
                run = await client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=outputs,
                )
                continue
            # queued, in_progress, etc.
            await asyncio.sleep(1)
    except Exception as e:
        logger.exception("OpenAI Assistant run failed: %s", e)
    finally:
        complete_agent_session(session_id)
        logger.info("OpenAI Assistant run finished: session_id=%s", session_id)


async def run_agent_loop(session_id: str, challenge_id: str, agent_id: str) -> None:
    """
    Run the agent loop in-process: load challenge, submit prompts via LLM, record turns, complete.
    Mirrors modal_agent/app.py so behavior is identical.
    """
    session = get_session(session_id)
    if session is None:
        logger.error("Agent run: session %s not found", session_id)
        return
    if session.status != "active":
        logger.warning("Agent run: session %s not active", session_id)
        return

    agent = get_agent_by_id(agent_id)
    challenge = get_challenge_by_id(challenge_id)
    if not agent or not challenge:
        logger.error("Agent run: agent or challenge not found")
        return

    if agent_id == "claude-sdk":
        await _run_agent_loop_claude_sdk(session_id, challenge_id, agent_id)
        return
    if agent_id == "openai-assistant":
        await _run_agent_loop_openai_assistant(session_id, challenge_id, agent_id)
        return

    from config import settings
    model_used = agent.model or settings.default_model
    brief = _challenge_brief(challenge)

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

            response = await llm.generate(
                prompt,
                conversation_history=history if history else None,
                system_prompt=system_prompt,
            )

            accuracy = 0.0
            if challenge.target_code:
                accuracy = compute_accuracy_text(
                    response.generated_code, challenge.target_code
                )

            turn = Turn(
                turn_number=len(session.turns) + 1,
                prompt_text=prompt,
                prompt_tokens=response.prompt_tokens,
                response_text=response.response_text,
                response_tokens=response.response_tokens,
                generated_code=response.generated_code,
                accuracy_at_turn=accuracy,
                timestamp=time.time(),
            )
            add_turn(session_id, turn)
            session = get_session(session_id)
            if not session:
                break

            if accuracy >= ACCURACY_THRESHOLD:
                break
            if "DONE" in (response.response_text or "").upper():
                break

        complete_agent_session(session_id)
        logger.info("Agent run completed: session_id=%s turns=%s", session_id, turn_count)
    except Exception as e:
        logger.exception("Agent run failed: session_id=%s %s", session_id, e)
