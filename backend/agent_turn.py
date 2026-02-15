"""
Internal: execute one prompt turn (LLM + record) and complete session. Used by HTTP endpoint and in-process agent runners.
"""

import time
from collections.abc import Awaitable, Callable

from challenges import get_challenge_by_id
from llm import LLM, REPLICATE_UI_SYSTEM_PROMPT
from evaluation.scoring import compute_accuracy_text, compute_composite_score
from sessions import (
    add_turn,
    add_to_leaderboard,
    complete_session,
    get_session,
    LeaderboardEntry,
    Turn,
)

# Default LLM instance (same as main.llm)
_default_llm: LLM | None = None


def _get_llm():
    global _default_llm
    if _default_llm is None:
        from config import settings
        _default_llm = LLM()
    return _default_llm


async def execute_prompt_turn(
    session_id: str,
    prompt: str,
    *,
    model: str | None = None,
    system_prompt: str | None = None,
    on_progress: Callable[[int], Awaitable[None]] | None = None,
    reference_image_data_url: str | None = None,
) -> dict:
    """
    Run one turn: build history, call LLM, compute accuracy, add_turn.
    Returns dict with response_text, generated_code, accuracy, prompt_tokens, response_tokens, turn_number.
    If reference_image_data_url is provided (reference page screenshot), uses vision model for UI replication.
    If on_progress is provided, uses streaming. Caller must ensure session exists and is active.
    """
    session = get_session(session_id)
    if session is None:
        raise ValueError("Session not found")
    challenge = get_challenge_by_id(session.challenge_id)
    if challenge is None:
        raise ValueError("Challenge not found")

    history: list[dict] = []
    for t in session.turns:
        history.append({"role": "user", "content": t.prompt_text})
        history.append({"role": "assistant", "content": t.response_text})

    from config import settings
    import logging
    _log = logging.getLogger(__name__)
    llm = _get_llm()
    if reference_image_data_url:
        model = model or getattr(settings, "vision_model", None) or session.model_used
        system_prompt = system_prompt or REPLICATE_UI_SYSTEM_PROMPT
        _log.info(
            "Vision turn: model=%s, image_data_url len=%d",
            model,
            len(reference_image_data_url or ""),
        )
    else:
        model = model or session.model_used
    llm_instance = LLM(model=model) if model != llm.model else llm

    if on_progress is not None:
        full_response = ""
        async for chunk in llm_instance.stream(
            prompt,
            conversation_history=history if history else None,
            system_prompt=system_prompt,
            image_data_url=reference_image_data_url,
        ):
            full_response += chunk
            # ~4 chars per token estimate
            est_tokens = max(0, len(full_response) // 4)
            await on_progress(est_tokens)

        generated_code = LLM.extract_code_blocks(full_response)
        accuracy = 0.0
        if challenge.target_code:
            accuracy = compute_accuracy_text(generated_code, challenge.target_code)
        est_prompt_tokens = len(prompt.split()) * 2
        est_response_tokens = len(full_response.split()) * 2

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
        return {
            "response_text": full_response,
            "generated_code": generated_code,
            "accuracy": accuracy,
            "prompt_tokens": est_prompt_tokens,
            "response_tokens": est_response_tokens,
            "turn_number": turn.turn_number,
        }
    else:
        response = await llm_instance.generate(
            prompt,
            conversation_history=history if history else None,
            system_prompt=system_prompt,
            image_data_url=reference_image_data_url,
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
        return {
            "response_text": response.response_text,
            "generated_code": response.generated_code,
            "accuracy": accuracy,
            "prompt_tokens": response.prompt_tokens,
            "response_tokens": response.response_tokens,
            "turn_number": turn.turn_number,
        }


def complete_agent_session(session_id: str) -> None:
    """
    Compute scores, mark session completed, add to leaderboard.
    Caller must ensure session exists and is active.
    """
    session = get_session(session_id)
    if session is None or session.status != "active":
        return
    challenge = get_challenge_by_id(session.challenge_id)
    if challenge is None:
        return
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
