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
from scoring import compute_accuracy_text
from sessions import get_session, add_turn, Turn

logger = logging.getLogger(__name__)

MAX_TURNS = 10
ACCURACY_THRESHOLD = 0.95
COT_SYSTEM_PROMPT = (
    "You are a careful reasoner. Think step by step: analyze the requirement, "
    "plan the solution, then write the code. Put your reasoning first, then output "
    "the final code in a single markdown code block."
)


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

    description = challenge.description or ""
    title = challenge.title or "Challenge"

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
    options = ClaudeAgentOptions(
        mcp_servers={"lucidly-challenge": custom_server},
        allowed_tools=["mcp__lucidly-challenge__submit_prompt"],
        system_prompt=(
            f"You are completing a coding challenge.\n\n"
            f"Challenge: {title}\n\n{description}\n\n"
            "Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and an accuracy score. "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE."
        ),
        max_turns=MAX_TURNS,
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            prompt = f"Complete this coding challenge. Use the submit_prompt tool to generate and refine code. Challenge: {title}\n\n{description}"
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

    description = challenge.description or ""
    title = challenge.title or "Challenge"
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    assistant = await client.beta.assistants.create(
        name="Lucidly Challenge Agent",
        instructions=(
            f"You are completing a coding challenge.\n\n"
            f"Challenge: {title}\n\n{description}\n\n"
            "Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and accuracy. "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE."
        ),
        model=agent.model,
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

    description = challenge.description or ""
    title = challenge.title or "Challenge"

    from config import settings
    model_used = agent.model or settings.default_model

    def first_turn_prompt(aid: str) -> str:
        base = f"Challenge: {title}\n\n{description}\n\n"
        if aid == "openai-cot":
            return (
                base
                + "Think step by step. First analyze the requirement, then plan the solution, then write the code. "
                "Put your reasoning first, then output the final code in a single markdown code block."
            )
        return (
            base
            + "Generate complete, runnable code that fulfills this challenge. "
            "Output only the code, or use a single markdown code block."
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
