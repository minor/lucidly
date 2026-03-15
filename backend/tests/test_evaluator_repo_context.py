"""Tests for evaluator routing when challenge has repo_context."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from challenges import Challenge, RepoContext, TestCase
from evaluation.evaluator import ChallengeEvaluator


REPO_CONTEXT = RepoContext(
    owner="acme",
    repo="myrepo",
    base_sha="base123",
    file_path="src/parser.py",
    challenge_test_ids=["tests/test_parser.py::test_tok"],
)

CHALLENGE_WITH_REPO_CTX = Challenge(
    id="c1",
    title="Fix tokenize",
    description="buggy tokenize",
    category="function",
    difficulty="medium",
    user_id="user|123",
    repo_context=REPO_CONTEXT,
    test_files=[{"path": "tests/test_parser.py", "content": "def test_tok(): pass"}],
)


@pytest.mark.asyncio
async def test_evaluate_routes_to_repo_context_when_present():
    """When challenge.repo_context is set, routes to _evaluate_with_repo_context."""
    mock_results = [{"name": "tests/test_parser.py::test_tok", "passed": True, "message": ""}]
    evaluator = ChallengeEvaluator()

    with patch("integrations.store.get_integration", return_value="ghp_tok"):
        with patch(
            "evaluation.evaluator.run_in_repo_context",
            new_callable=AsyncMock,
            return_value=(mock_results, "1 passed"),
        ) as mock_run:
            result = await evaluator._evaluate_function(
                CHALLENGE_WITH_REPO_CTX, "def tokenize(s): return []", None
            )

    mock_run.assert_called_once()
    assert result.accuracy == 1.0
    assert result.test_results == [True]
    assert result.details["source"] == "repo_context"
    assert result.execution_output == "1 passed"


@pytest.mark.asyncio
async def test_evaluate_returns_error_when_github_token_missing():
    evaluator = ChallengeEvaluator()

    with patch("integrations.store.get_integration", return_value=None):
        result = await evaluator._evaluate_function(
            CHALLENGE_WITH_REPO_CTX, "def tokenize(s): return []", None
        )

    assert result.accuracy == 0.0
    assert result.details["error"] == "github_token_missing"


@pytest.mark.asyncio
async def test_evaluate_uses_local_path_when_no_repo_context():
    """Without repo_context, uses existing run_function_tests_local path."""
    challenge_no_ctx = Challenge(
        id="c2",
        title="Sort list",
        description="sort",
        category="function",
        difficulty="easy",
        test_suite=[TestCase(input="sort([3,1,2])", expected_output="[1,2,3]")],
    )
    evaluator = ChallengeEvaluator()

    with patch("evaluation.evaluator.run_function_tests_local", return_value=(1.0, [True])):
        result = await evaluator._evaluate_function(
            challenge_no_ctx, "def sort(lst): return sorted(lst)", None
        )

    assert result.accuracy == 1.0


@pytest.mark.asyncio
async def test_evaluate_handles_execution_failure():
    """run_in_repo_context returning execution_failed result → accuracy=0."""
    failed_results = [{"name": "execution_failed", "passed": False, "message": "timeout"}]
    evaluator = ChallengeEvaluator()

    with patch("integrations.store.get_integration", return_value="ghp_tok"):
        with patch(
            "evaluation.evaluator.run_in_repo_context",
            new_callable=AsyncMock,
            return_value=(failed_results, ""),
        ):
            result = await evaluator._evaluate_function(
                CHALLENGE_WITH_REPO_CTX, "def tokenize(s): return []", None
            )

    assert result.accuracy == 0.0
    assert result.test_results == [False]
