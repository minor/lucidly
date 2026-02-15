"""Composite scoring engine for No Shot challenges.

Score = Accuracy * (
        0.30 * Speed
      + 0.25 * TokenEfficiency
      + 0.45 * TurnEfficiency
      )

All sub-scores are on a 0-1000 scale; the composite is also 0-1000.
"""

import math
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


def calculate_prompt_score(accuracy, time_seconds, cost_dollars, base_rating=500):
    """
    Calculate an ELO-style score for prompt performance.

    Parameters:
    - accuracy: 0-100 (percentage)
    - time_seconds: time taken in seconds
    - cost_dollars: cost in dollars
    - base_rating: starting ELO (default 500, midpoint of 0-1000)

    Returns:
    - score: ELO-style rating (0-1000)
    - breakdown: dict showing component contributions
    """

    # Normalize accuracy to 0-1 range, then apply power curve to penalize low accuracy
    # Power of 2 means: 100% → 1.0, 50% → 0.25, 25% → 0.0625, 10% → 0.01
    accuracy_normalized = max(0, min(accuracy, 100)) / 100
    accuracy_component = math.pow(accuracy_normalized, 2)
    # Map to -1 to +1: 0→-1, 0.5→0 (which is ~71% accuracy), 1→+1
    accuracy_component = accuracy_component * 2 - 1

    # Time penalty: exponential decay (24s = 0, 12s = +0.5, 48s = -0.5)
    # Using 24s as reference point
    time_reference = 60
    time_component = -math.tanh((time_seconds - time_reference) / time_reference)

    # Cost penalty: logarithmic scale (lower is better)
    # $0.0020 as reference
    cost_reference = 0.0020
    if cost_dollars > 0:
        cost_component = -math.log10(cost_dollars / cost_reference) 
        cost_component = max(-1, min(1, cost_component))  # clamp to [-1, 1]
    else:
        cost_component = 1  # free is best

    # Weighted combination (turns excluded — directly correlated with time)
    weights = {
        'accuracy': 0.70,   # Most important
        'time': 0.15,
        'cost': 0.15
    }

    combined_score = (
        weights['accuracy'] * accuracy_component +
        weights['time'] * time_component +
        weights['cost'] * cost_component
    )

    # Convert to 0-1000 scale: -1 maps to 0, 0 maps to 500, +1 maps to 1000
    elo_score = base_rating + (combined_score * 500)
    elo_score = max(0, min(1000, elo_score))  # clamp to [0, 1000]

    breakdown = {
        'accuracy_contribution': weights['accuracy'] * accuracy_component * 500,
        'time_contribution': weights['time'] * time_component * 500,
        'cost_contribution': weights['cost'] * cost_component * 500,
        'raw_components': {
            'accuracy': accuracy_component,
            'time': time_component,
            'cost': cost_component
        }
    }

    return round(elo_score), breakdown


def compute_composite_score(
    accuracy: float,
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
    difficulty: str = "medium",
    total_cost: float = 0.0,
) -> dict:
    """
    Compute the full composite score using ELO-style rating.

    Parameters:
    - accuracy: 0-1 (fraction of tests passed / similarity)
    - elapsed_sec: time taken in seconds
    - total_tokens: total tokens used (unused in ELO model, kept for API compat)
    - total_turns: number of conversation turns
    - difficulty: challenge difficulty (unused in ELO model, kept for API compat)
    - total_cost: cost in dollars

    Returns a dict with individual sub-scores and the ELO composite (0-1000).
    """
    # Convert accuracy from 0-1 fraction to 0-100 percentage for the ELO function
    accuracy_pct = accuracy * 100

    elo_score, breakdown = calculate_prompt_score(
        accuracy=accuracy_pct,
        time_seconds=elapsed_sec,
        cost_dollars=total_cost,
    )

    # Map raw components (-1 to +1) back to 0-1000 scale for sub-score display
    raw = breakdown["raw_components"]

    return {
        "accuracy_score": round((raw["accuracy"] + 1) / 2 * 1000),
        "speed_score": round((raw["time"] + 1) / 2 * 1000),
        "token_score": round((raw["cost"] + 1) / 2 * 1000),
        "turn_score": 0,  # turns no longer factored into ELO
        "composite_score": elo_score,
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


