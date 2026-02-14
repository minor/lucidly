"""
Modal agent runner: runs a single agent on a challenge by calling the Lucidly backend.
Deploy: modal deploy app.py
Run (for testing): modal run app.py --session-id <id> --challenge-id <id> --agent-id claude-direct
"""

import os

import modal

app = modal.App("lucidly-agent")

# Image with httpx for HTTP calls
image = modal.Image.debian_slim(python_version="3.11").pip_install("httpx")

# Max turns per run
MAX_TURNS = 10
ACCURACY_THRESHOLD = 0.95


@app.function(image=image, timeout=600)
def run_agent(
    session_id: str,
    challenge_id: str,
    agent_id: str,
    backend_url: str,
    agent_token: str,
):
    """
    Run the agent loop: fetch challenge, submit prompts to backend, complete session.
    backend_url: e.g. https://your-api.com or http://host.docker.internal:8000 for local
    agent_token: X-Agent-Token value for auth (can be empty if not configured)
    """
    import httpx

    base = backend_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if agent_token:
        headers["X-Agent-Token"] = agent_token

    # 1) Load challenge
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{base}/api/challenges/{challenge_id}", headers=headers)
        r.raise_for_status()
        challenge = r.json()

    description = challenge.get("description", "")
    title = challenge.get("title", "Challenge")
    category = challenge.get("category", "ui")

    COT_SYSTEM_PROMPT = (
        "You are a careful reasoner. Think step by step: analyze the requirement, "
        "plan the solution, then write the code. Put your reasoning first, then output "
        "the final code in a single markdown code block."
    )

    def first_turn_prompt(strategy: str) -> str:
        base = f"Challenge: {title}\n\n{description}\n\n"
        if strategy == "openai_cot":
            return (
                base
                + "Think step by step. First analyze the requirement, then plan the solution, then write the code. "
                "Put your reasoning first, then output the final code in a single markdown code block."
            )
        # claude_direct or default
        return (
            base
            + "Generate complete, runnable code that fulfills this challenge. "
            "Output only the code, or use a single markdown code block."
        )

    # 2) Agent loop: strategy-specific first prompt, then iterate if needed
    turn = 0
    while turn < MAX_TURNS:
        turn += 1
        if turn == 1:
            prompt = first_turn_prompt(agent_id)
            payload: dict = {"prompt": prompt}
            if agent_id == "openai-cot":
                payload["system_prompt"] = COT_SYSTEM_PROMPT
        else:
            # Next turn: ask to improve (in a real scenario we'd pass last code/accuracy)
            prompt = (
                "Review the previous response and improve the code if accuracy was not 100%. "
                "Otherwise respond with: DONE"
            )
            payload = {"prompt": prompt}

        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{base}/api/sessions/{session_id}/prompt",
                headers=headers,
                json=payload,
            )
            if r.status_code != 200:
                raise RuntimeError(f"Prompt failed: {r.status_code} {r.text}")
            data = r.json()

        accuracy = data.get("accuracy", 0.0)
        if accuracy >= ACCURACY_THRESHOLD:
            break
        # Optional: check if model said DONE
        if "DONE" in (data.get("response_text") or "").upper():
            break

    # 3) Complete session
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{base}/api/sessions/{session_id}/complete",
            headers=headers,
        )
        r.raise_for_status()

    return {"session_id": session_id, "turns": turn, "status": "completed"}


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
