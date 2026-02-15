"""Evaluation module for No Shot challenges.

This module contains all evaluation-related functionality:
- Test generation
- Code evaluation
- Scoring
"""

from .evaluator import ChallengeEvaluator, EvaluationResult
from .test_generator import TestGenerator, GeneratedTestSuite
from .scoring import (
    compute_composite_score,
    compute_composite_score_efficiency_only,
    compute_accuracy_function,
    compute_accuracy_text,
    run_function_tests_detailed,
)

__all__ = [
    "ChallengeEvaluator",
    "EvaluationResult",
    "TestGenerator",
    "GeneratedTestSuite",
    "compute_composite_score",
    "compute_composite_score_efficiency_only",
    "compute_accuracy_function",
    "compute_accuracy_text",
    "run_function_tests_detailed",
]
