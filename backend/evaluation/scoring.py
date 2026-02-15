"""Composite scoring engine for No Shot challenges.

Score = Accuracy * (
        0.30 * Speed
      + 0.25 * TokenEfficiency
      + 0.45 * TurnEfficiency
      )

All sub-scores are on a 0-1000 scale; the composite is also 0-1000.
"""

import sys
from pathlib import Path

# Add parent directory to path for absolute imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


def compute_accuracy_function(test_results: list[bool]) -> float:
    """Accuracy for function challenges: tests passed / total tests."""
    if not test_results:
        return 0.0
    return sum(test_results) / len(test_results)


def compute_accuracy_text(generated: str, target: str) -> float:
    """Simple text similarity for code/debug challenges (MVP)."""
    if not target:
        return 0.0
    # Normalize whitespace for comparison
    gen_tokens = generated.split()
    tgt_tokens = target.split()
    if not tgt_tokens:
        return 0.0
    common = len(set(gen_tokens) & set(tgt_tokens))
    return common / max(len(tgt_tokens), 1)


def compute_speed_score(elapsed_sec: float, difficulty: str = "medium") -> float:
    """Speed score: inverse of time, normalized against difficulty baseline."""
    baselines = settings.SCORING_BASELINES.get(difficulty, settings.SCORING_BASELINES["medium"])
    median = baselines["time"]
    
    if elapsed_sec <= 0:
        return 1.0
    # Ratio: faster than median → score > 0.5
    ratio = median / elapsed_sec
    return min(ratio, 2.0) / 2.0  # cap at 1.0


def compute_token_efficiency(total_tokens: int, difficulty: str = "medium") -> float:
    """Token efficiency: fewer tokens → higher score."""
    baselines = settings.SCORING_BASELINES.get(difficulty, settings.SCORING_BASELINES["medium"])
    median = baselines["tokens"]
    
    if total_tokens <= 0:
        return 1.0
    ratio = median / total_tokens
    return min(ratio, 2.0) / 2.0


def compute_turn_efficiency(total_turns: int, difficulty: str = "medium") -> float:
    """Turn efficiency: fewer turns → higher score."""
    baselines = settings.SCORING_BASELINES.get(difficulty, settings.SCORING_BASELINES["medium"])
    median = baselines["turns"]
    
    if total_turns <= 0:
        return 1.0
    ratio = median / total_turns
    return min(ratio, 2.0) / 2.0


def compute_composite_score(
    accuracy: float,
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
    difficulty: str = "medium",
) -> dict:
    """
    Compute the full composite score.

    Returns a dict with individual sub-scores (0-1000) and the composite.
    """
    speed = compute_speed_score(elapsed_sec, difficulty)
    token_eff = compute_token_efficiency(total_tokens, difficulty)
    turn_eff = compute_turn_efficiency(total_turns, difficulty)

    composite = accuracy * (
        0.30 * speed
        + 0.25 * token_eff
        + 0.45 * turn_eff
    )

    return {
        "accuracy_score": round(accuracy * 1000),
        "speed_score": round(speed * 1000),
        "token_score": round(token_eff * 1000),
        "turn_score": round(turn_eff * 1000),
        "composite_score": round(composite * 1000),
    }


def compute_composite_score_efficiency_only(
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
    difficulty: str = "medium",
) -> dict:
    """
    Composite score for challenges with no accuracy (e.g. product/PRD).
    Score = weighted efficiency only (speed, tokens, turns), scaled 0–700
    so the max is 700 and 1000 is reserved for coding with perfect accuracy.
    """
    speed = compute_speed_score(elapsed_sec, difficulty)
    token_eff = compute_token_efficiency(total_tokens, difficulty)
    turn_eff = compute_turn_efficiency(total_turns, difficulty)
    composite = 0.30 * speed + 0.25 * token_eff + 0.45 * turn_eff
    return {
        "accuracy_score": 0,
        "speed_score": round(speed * 1000),
        "token_score": round(token_eff * 1000),
        "turn_score": round(turn_eff * 1000),
        "composite_score": round(composite * 700),
    }


async def run_function_tests(sandbox_id: str, code: str, test_suite: list[dict]) -> list[bool]:
    """
    Run test cases via a persistent Modal sandbox. Returns list of booleans.
    """
    from sandbox import run_tests_in_sandbox
    detailed = await run_tests_in_sandbox(sandbox_id, code, test_suite)
    return [r["passed"] for r in detailed]


async def run_function_tests_detailed(sandbox_id: str, code: str, test_suite: list[dict]) -> list[dict]:
    """
    Run test cases via a persistent Modal sandbox. Returns detailed results.
    """
    from sandbox import run_tests_in_sandbox
    return await run_tests_in_sandbox(sandbox_id, code, test_suite)


