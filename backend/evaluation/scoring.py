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

# from config import settings


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


def calculate_prompt_score(accuracy, time_seconds, cost_dollars, num_turns, base_rating=500):
    """
    Calculate an ELO-style score for prompt performance.

    Parameters:
    - accuracy: 0-100 (percentage)
    - time_seconds: time taken in seconds
    - cost_dollars: cost in dollars
    - num_turns: number of conversation turns
    - base_rating: starting ELO (default 500, midpoint of 0-1000)

    Returns:
    - score: ELO-style rating (0-1000)
    - breakdown: dict showing component contributions

    Changes from v1:
    - Accuracy: power 1.5 (was 2) — softer curve, 67% now contributes positively
    - Time: reference 90s (was 60s), gentler slope via 1.5× divisor
    - Cost: reference $0.05 (was $0.002) — realistic for modern LLM calls
    - Turns: NEW metric — 1 turn = +1, 3 turns = neutral, 10+ = near -1
    - Weights: accuracy 60%, cost 15%, turns 15%, time 10%
    """

    # Hard floor: 0% accuracy always yields a 0 score.
    if accuracy <= 0:
        return 0, {
            "accuracy_contribution": 0.0,
            "time_contribution": 0.0,
            "cost_contribution": 0.0,
            "turns_contribution": 0.0,
            "low_accuracy_penalty_multiplier": 0.0,
            "raw_components": {
                "accuracy": -1.0,
                "time": 0.0,
                "cost": 0.0,
                "turns": 0.0,
            },
        }

    # --- ACCURACY ---
    # Power of 1.5 instead of 2 for a softer curve.
    # 100% → 1.0, 67% → 0.548, 50% → 0.354, 25% → 0.125
    # Break-even (~0 component) is at ~63% accuracy.
    accuracy_normalized = max(0, min(accuracy, 100)) / 100
    accuracy_component = math.pow(accuracy_normalized, 1.5)
    accuracy_component = accuracy_component * 2 - 1  # Map to [-1, +1]

    # --- TIME ---
    # Reference: 160 seconds (neutral point). Divisor of 45 for good spread.
    # 10s → +1.0, 60s → +0.97, 120s → +0.66, 160s → 0, 200s → -0.66, 300s → -0.999
    time_reference = 160
    time_component = math.tanh((time_reference - time_seconds) / 45)

    # --- COST ---
    # Reference: $0.05 (realistic midpoint for LLM API calls).
    # $0.05 → 0, $0.005 → +1, $0.50 → -1
    cost_reference = 0.05
    if cost_dollars > 0:
        cost_component = -math.log10(cost_dollars / cost_reference)
        cost_component = max(-1, min(1, cost_component))  # clamp to [-1, 1]
    else:
        cost_component = 1  # free is best

    # --- TURNS ---
    # Linear mapping across 1-4 turns (max is 4).
    # 1 turn → +1.0, 2 turns → +0.33, 3 turns → -0.33, 4 turns → -1.0
    num_turns_clamped = max(1, min(num_turns, 4))
    turns_component = 1 - 2 * (num_turns_clamped - 1) / 3

    # --- WEIGHTED COMBINATION ---
    weights = {
        "accuracy": 0.60,  # Most important
        "time": 0.15,      # Reduced from 0.15
        "cost": 0.15,
        "turns": 0.10,     # New
    }

    combined_score = (
        weights["accuracy"] * accuracy_component
        + weights["time"] * time_component
        + weights["cost"] * cost_component
        + weights["turns"] * turns_component
    )

    # Convert to 0-1000 scale: -1 → 0, 0 → 500, +1 → 1000
    elo_score = base_rating + (combined_score * 500)

    # Extra punishment for very low accuracy: under 20% gets a steep penalty.
    low_accuracy_penalty_multiplier = 1.0
    if accuracy_normalized < 0.20:
        low_accuracy_penalty_multiplier = math.pow(accuracy_normalized / 0.20, 2)
        elo_score *= low_accuracy_penalty_multiplier

    elo_score = max(0, min(1000, elo_score))  # clamp to [0, 1000]

    raw = {
        "accuracy": accuracy_component,
        "time": time_component,
        "cost": cost_component,
        "turns": turns_component,
    }

    breakdown = {
        "accuracy_contribution": weights["accuracy"] * accuracy_component * 500,
        "time_contribution": weights["time"] * time_component * 500,
        "cost_contribution": weights["cost"] * cost_component * 500,
        "turns_contribution": weights["turns"] * turns_component * 500,
        "low_accuracy_penalty_multiplier": low_accuracy_penalty_multiplier,
        "raw_components": raw,
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
    - total_tokens: total tokens used (kept for API compat)
    - total_turns: number of conversation turns
    - difficulty: challenge difficulty (kept for API compat)
    - total_cost: cost in dollars

    Returns a dict with individual sub-scores and the ELO composite (0-1000).
    """
    accuracy_pct = accuracy * 100

    elo_score, breakdown = calculate_prompt_score(
        accuracy=accuracy_pct,
        time_seconds=elapsed_sec,
        cost_dollars=total_cost,
        num_turns=total_turns,
    )

    raw = breakdown["raw_components"]

    return {
        "accuracy_score": round((raw["accuracy"] + 1) / 2 * 1000),
        "speed_score": round((raw["time"] + 1) / 2 * 1000),
        "token_score": round((raw["cost"] + 1) / 2 * 1000),
        "turn_score": round((raw["turns"] + 1) / 2 * 1000),
        "composite_score": elo_score,
    }

def compute_function_composite_score(
    accuracy: float,
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
    total_cost: float = 0.0,
) -> dict:
    """
    Composite score for function/debug challenges.

    Weights: Accuracy 80%, Turns 10%, Time 5%, Cost 5%.
    Uses the same component curves as standard scoring.

    Parameters:
    - accuracy: 0-1 (fraction of tests passed)
    - elapsed_sec: time taken in seconds
    - total_tokens: total tokens used (kept for API compat)
    - total_turns: number of conversation turns (max 4)
    - total_cost: cost in dollars
    """
    accuracy_pct = accuracy * 100

    if accuracy_pct <= 0:
        return {
            "accuracy_score": 0,
            "speed_score": 500,
            "token_score": 500,
            "turn_score": 500,
            "composite_score": 0,
        }

    # --- ACCURACY --- (same power-1.5 curve)
    accuracy_normalized = max(0, min(accuracy_pct, 100)) / 100
    accuracy_component = math.pow(accuracy_normalized, 1.5)
    accuracy_component = accuracy_component * 2 - 1

    # --- TIME --- (same tanh curve, 160s neutral)
    time_reference = 160
    time_component = math.tanh((time_reference - elapsed_sec) / 45)

    # --- COST --- (same log10 curve, $0.05 neutral)
    cost_reference = 0.005
    if total_cost > 0:
        cost_component = -math.log10(total_cost / cost_reference)
        cost_component = max(-1, min(1, cost_component))
    else:
        cost_component = 1

    # --- TURNS --- (linear across 1-4)
    num_turns_clamped = max(1, min(total_turns, 4))
    turns_component = 1 - 2 * (num_turns_clamped - 1) / 3

    # --- WEIGHTED COMBINATION ---
    combined = (
        0.80 * accuracy_component
        + 0.05 * turns_component
        + 0.10 * time_component
        + 0.05 * cost_component
    )

    composite = 500 + combined * 500

    # Low-accuracy penalty (same as standard scoring)
    if accuracy_normalized < 0.20:
        penalty = math.pow(accuracy_normalized / 0.20, 2)
        composite *= penalty

    composite = max(0, min(1000, round(composite)))

    return {
        "accuracy_score": round((accuracy_component + 1) / 2 * 1000),
        "speed_score": round((time_component + 1) / 2 * 1000),
        "token_score": round((cost_component + 1) / 2 * 1000),
        "turn_score": round((turns_component + 1) / 2 * 1000),
        "composite_score": composite,
    }


def compute_prd_composite_score(
    prd_score_100: int,
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
    total_cost: float = 0.0,
) -> dict:
    """
    Composite score for PRD/product challenges.

    Weights: PRD quality 80%, Turns 10%, Time 5%, Cost 5%.
    All components are mapped to [-1, +1], then combined into a 0-1000 scale.

    Parameters:
    - prd_score_100: LLM-graded PRD quality score (0-100)
    - elapsed_sec: time taken in seconds
    - total_tokens: total tokens used (kept for API compat)
    - total_turns: number of conversation turns (max 10 for product)
    - total_cost: cost in dollars
    """
    # --- PRD QUALITY (replaces accuracy) ---
    prd_normalized = max(0, min(prd_score_100, 100)) / 100
    prd_component = prd_normalized * 2 - 1  # 0→-1, 50→0, 100→+1

    # --- TIME --- (same curve as standard scoring)
    time_reference = 300
    time_component = math.tanh((time_reference - elapsed_sec) / 45)

    # --- COST --- (same curve as standard scoring)
    cost_reference = 0.005
    if total_cost > 0:
        cost_component = -math.log10(total_cost / cost_reference)
        cost_component = max(-1, min(1, cost_component))
    else:
        cost_component = 1

    # --- TURNS --- (linear across 1-10 for product challenges)
    num_turns_clamped = max(1, min(total_turns, 10))
    turns_component = 1 - 2 * (num_turns_clamped - 1) / 9

    # --- WEIGHTED COMBINATION ---
    combined = (
        0.80 * prd_component
        + 0.10 * turns_component
        + 0.05 * time_component
        + 0.05 * cost_component
    )

    composite = 500 + combined * 500
    composite = max(0, min(1000, round(composite)))

    return {
        "accuracy_score": round((prd_component + 1) / 2 * 1000),
        "speed_score": round((time_component + 1) / 2 * 1000),
        "token_score": round((cost_component + 1) / 2 * 1000),
        "turn_score": round((turns_component + 1) / 2 * 1000),
        "composite_score": composite,
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


