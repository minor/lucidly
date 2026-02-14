"""
Modal agent runner: runs a single agent on a challenge by calling the Lucidly backend.
Supports simple loop (claude-direct, openai-cot), Claude Agent SDK (claude-sdk), and OpenAI Assistant (openai-assistant).
Deploy: modal deploy app.py
Run (for testing): modal run app.py --session-id <id> --challenge-id <id> --agent-id claude-direct
"""

import asyncio
import os
from typing import Any

import modal

app = modal.App("lucidly-agent")

# Image: httpx for HTTP; claude-agent-sdk for Claude SDK; openai for Assistants API
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "httpx",
    "claude-agent-sdk",
    "openai",
)

# Max turns per run
MAX_TURNS = 10
ACCURACY_THRESHOLD = 0.95


@app.function(image=image, timeout=600)
async def run_agent(
    session_id: str,
    challenge_id: str,
    agent_id: str,
    backend_url: str,
    agent_token: str,
):
    """
    Run the agent loop: fetch challenge, submit prompts to backend, complete session.
    For claude-sdk uses the Claude Agent SDK with a submit_prompt tool that POSTs to the backend.
    """
    import httpx

    base = backend_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if agent_token:
        headers["X-Agent-Token"] = agent_token

    # 1) Load challenge
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        r = await http_client.get(
            f"{base}/api/challenges/{challenge_id}", headers=headers
        )
        r.raise_for_status()
        challenge = r.json()

    def _challenge_brief(c: dict) -> str:
        title = c.get("title") or "Challenge"
        description = c.get("description") or ""
        embed_url = c.get("embed_url")
        image_url = c.get("image_url")
        starter_code = c.get("starter_code")
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

    brief = _challenge_brief(challenge)

    if agent_id == "claude-sdk":
        return await _run_claude_sdk(
            session_id=session_id,
            challenge_id=challenge_id,
            base_url=base,
            headers=headers,
            brief=brief,
        )
    if agent_id == "openai-assistant":
        return await _run_openai_assistant(
            session_id=session_id,
            base_url=base,
            headers=headers,
            brief=brief,
            challenge=challenge,
        )

    # Simple loop for claude-direct, openai-cot
    COT_SYSTEM_PROMPT = (
        "You are a careful reasoner. Think step by step: analyze the requirement, "
        "plan the solution, then write the code. Put your reasoning first, then output "
        "the final code in a single markdown code block."
    )

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

    turn = 0
    prev_had_code = True
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        while turn < MAX_TURNS:
            turn += 1
            if turn == 1:
                prompt = first_turn_prompt(agent_id)
                payload: dict = {"prompt": prompt}
                if agent_id == "openai-cot":
                    payload["system_prompt"] = COT_SYSTEM_PROMPT
            else:
                if not prev_had_code:
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
                payload = {"prompt": prompt}

            r = await http_client.post(
                f"{base}/api/sessions/{session_id}/prompt",
                headers=headers,
                json=payload,
            )
            if r.status_code != 200:
                raise RuntimeError(f"Prompt failed: {r.status_code} {r.text}")
            data = r.json()

            prev_had_code = bool((data.get("generated_code") or "").strip())

            accuracy = data.get("accuracy", 0.0)
            if accuracy >= ACCURACY_THRESHOLD:
                break
            if "DONE" in (data.get("response_text") or "").upper():
                break

        r = await http_client.post(
            f"{base}/api/sessions/{session_id}/complete",
            headers=headers,
        )
        r.raise_for_status()

    return {"session_id": session_id, "turns": turn, "status": "completed"}


async def _run_claude_sdk(
    session_id: str,
    challenge_id: str,
    base_url: str,
    headers: dict,
    brief: str,
) -> dict:
    """Run Claude Agent SDK with a tool that POSTs prompts to the backend."""
    import httpx
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        create_sdk_mcp_server,
        tool,
    )

    @tool(
        "submit_prompt",
        "Send a prompt to the code generation API. Returns the model response, generated code snippet, and accuracy (0-1). Use this to generate and refine code for the challenge.",
        {"prompt": str},
    )
    async def submit_prompt_tool(args: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{base_url}/api/sessions/{session_id}/prompt",
                headers=headers,
                json={"prompt": args["prompt"]},
            )
            r.raise_for_status()
            data = r.json()
        snippet = (data.get("generated_code") or "")[:2000]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Response: {(data.get('response_text') or '')[:1500]}\n\nGenerated code (excerpt):\n{snippet}\n\nAccuracy: {data.get('accuracy', 0):.2f}",
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
            "You are completing a coding challenge. Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and an accuracy score. "
            "Your first tool call must ask for code that fulfills the challenge (the response will be run in a preview). "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE.\n\n"
            f"{brief}"
        ),
        max_turns=MAX_TURNS,
    )

    async with ClaudeSDKClient(options=options) as client:
        prompt = "Complete this coding challenge. Use the submit_prompt tool to generate and refine code. Your first response must request runnable code (HTML for UI challenges) in a markdown code block."
        await client.query(prompt)
        async for _ in client.receive_response():
            pass

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base_url}/api/sessions/{session_id}/complete",
            headers=headers,
        )
        r.raise_for_status()

    return {"session_id": session_id, "status": "completed"}


async def _run_openai_assistant(
    session_id: str,
    base_url: str,
    headers: dict,
    brief: str,
    challenge: dict,
) -> dict:
    """Run OpenAI Assistants API with submit_prompt function that POSTs to backend."""
    import json
    from openai import AsyncOpenAI

    # Use OpenAI from env (Modal secret or env)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url_openai = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_ASSISTANT_MODEL", "gpt-4o")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url_openai)

    assistant = await client.beta.assistants.create(
        name="Lucidly Challenge Agent",
        instructions=(
            "You are completing a coding challenge. Use the submit_prompt tool to send prompts to the code generation API. "
            "Each call returns the model's response, generated code, and accuracy. Your first tool call must request runnable code. "
            "Iterate until accuracy is 1.0 or you have tried enough. Then reply with DONE.\n\n"
            f"{brief}"
        ),
        model=model,
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
    while step < max_steps:
        step += 1
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run.status == "completed":
            break
        if run.status == "failed":
            break
        if run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            outputs = []
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                for tc in tool_calls:
                    name = getattr(tc.function, "name", "") or ""
                    if name != "submit_prompt":
                        outputs.append({"tool_call_id": tc.id, "output": "Unknown tool"})
                        continue
                    args = json.loads(
                        getattr(tc.function, "arguments", None) or "{}"
                    )
                    prompt = args.get("prompt", "")
                    r = await http_client.post(
                        f"{base_url}/api/sessions/{session_id}/prompt",
                        headers=headers,
                        json={"prompt": prompt},
                    )
                    r.raise_for_status()
                    data = r.json()
                    snippet = (data.get("generated_code") or "")[:1500]
                    output = f"Response: {(data.get('response_text') or '')[:1000]}\n\nGenerated code (excerpt):\n{snippet}\n\nAccuracy: {data.get('accuracy', 0):.2f}"
                    outputs.append({"tool_call_id": tc.id, "output": output})
            run = await client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=outputs,
            )
            continue
        await asyncio.sleep(1)

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base_url}/api/sessions/{session_id}/complete",
            headers=headers,
        )
        r.raise_for_status()

    return {"session_id": session_id, "status": "completed"}


@app.local_entrypoint()
def main():
    """CLI entrypoint for testing: modal run modal_agent/app.py --session-id <id> --challenge-id <id>"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--challenge-id", required=True)
    parser.add_argument("--agent-id", default="claude-direct")
    args = parser.parse_args()
    backend_url = os.environ.get("BACKEND_URL", "http://host.docker.internal:8000")
    agent_token = os.environ.get("AGENT_INTERNAL_SECRET", "")
    run_agent.remote(
        session_id=args.session_id,
        challenge_id=args.challenge_id,
        agent_id=args.agent_id,
        backend_url=backend_url,
        agent_token=agent_token,
    )
