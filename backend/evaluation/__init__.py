"""Evaluation module for Lucidly challenges.

This module contains all evaluation-related functionality:
- Test generation
- Code evaluation
- Vision comparison
- Scoring
"""

from .evaluator import ChallengeEvaluator, EvaluationResult
from .test_generator import TestGenerator, GeneratedTestSuite
from .vision_comparison import VisionComparator, VisionComparisonResult
from .scoring import (
    compute_composite_score,
    compute_accuracy_function,
    compute_accuracy_text,
    run_function_tests,
    run_function_tests_detailed,
)
from .screenshot_vision_integration import (
    capture_and_compare,
    capture_iframe_and_compare,
    compare_with_challenge_reference,
)

__all__ = [
    "ChallengeEvaluator",
    "EvaluationResult",
    "TestGenerator",
    "GeneratedTestSuite",
    "VisionComparator",
    "VisionComparisonResult",
    "compute_composite_score",
    "compute_accuracy_function",
    "compute_accuracy_text",
    "run_function_tests",
    "run_function_tests_detailed",
    "capture_and_compare",
    "capture_iframe_and_compare",
    "compare_with_challenge_reference",
]


