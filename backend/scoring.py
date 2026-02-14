"""Composite scoring engine for Lucidly challenges.

Score = 0.40 * Accuracy
      + 0.25 * Speed
      + 0.20 * TokenEfficiency
      + 0.15 * TurnEfficiency

All sub-scores are on a 0-1000 scale; the composite is also 0-1000.
"""

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


def compute_speed_score(elapsed_sec: float) -> float:
    """Speed score: inverse of time, normalized against median."""
    median = settings.median_time_sec
    if elapsed_sec <= 0:
        return 1.0
    # Ratio: faster than median → score > 0.5
    ratio = median / elapsed_sec
    return min(ratio, 2.0) / 2.0  # cap at 1.0


def compute_token_efficiency(total_tokens: int) -> float:
    """Token efficiency: fewer tokens → higher score."""
    median = settings.median_tokens
    if total_tokens <= 0:
        return 1.0
    ratio = median / total_tokens
    return min(ratio, 2.0) / 2.0


def compute_turn_efficiency(total_turns: int) -> float:
    """Turn efficiency: fewer turns → higher score."""
    median = settings.median_turns
    if total_turns <= 0:
        return 1.0
    ratio = median / total_turns
    return min(ratio, 2.0) / 2.0


def compute_composite_score(
    accuracy: float,
    elapsed_sec: float,
    total_tokens: int,
    total_turns: int,
) -> dict:
    """
    Compute the full composite score.

    Returns a dict with individual sub-scores (0-1000) and the composite.
    """
    speed = compute_speed_score(elapsed_sec)
    token_eff = compute_token_efficiency(total_tokens)
    turn_eff = compute_turn_efficiency(total_turns)

    composite = (
        0.40 * accuracy
        + 0.25 * speed
        + 0.20 * token_eff
        + 0.15 * turn_eff
    )

    return {
        "accuracy_score": round(accuracy * 1000),
        "speed_score": round(speed * 1000),
        "token_score": round(token_eff * 1000),
        "turn_score": round(turn_eff * 1000),
        "composite_score": round(composite * 1000),
    }


def run_function_tests(code: str, test_suite: list[dict]) -> list[bool]:
    """
    Execute generated code and run test cases against it (MVP approach).

    Each test case has an `input` expression and `expected_output` string.
    We exec() the code then eval() the input expression and compare.
    """
    results: list[bool] = []

    # Helper functions available in test context
    helpers = """
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def arr_to_list(arr):
    head = None
    for v in reversed(arr):
        head = ListNode(v, head)
    return head

def list_to_arr(node):
    result = []
    while node:
        result.append(node.val)
        node = node.next
    return result
"""

    namespace: dict = {}
    try:
        exec(helpers + "\n" + code, namespace)
    except Exception:
        return [False] * len(test_suite)

    for test in test_suite:
        try:
            actual = eval(test["input"], namespace)
            expected = eval(test["expected_output"], namespace)
            results.append(actual == expected)
        except Exception:
            results.append(False)

    return results
