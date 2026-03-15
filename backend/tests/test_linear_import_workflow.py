"""
End-to-end workflow tests for the Linear → GitHub → generate-challenge pipeline.

Covers four scenarios:
  1. Happy path  — Linear issue with GitHub PR, test file found → parse existing tests
  2. Diff fallback — PR found, but no test file → LLM generates from diff
  3. No GitHub    — user hasn't connected GitHub → LLM generates from issue only
  4. No PR link   — Linear issue has no GitHub attachment → LLM generates from issue only
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Uses fixtures from conftest.py: auth_client

# ---------------------------------------------------------------------------
# Shared realistic fixtures
# ---------------------------------------------------------------------------

LINEAR_ISSUE = {
    "id": "ISSUE-123",
    "identifier": "ENG-42",
    "title": "Fix off-by-one error in paginate()",
    "description": "The paginate function returns one extra item on the last page.",
    "branchName": "eng-42-fix-paginate",
    "url": "https://linear.app/myteam/issue/ENG-42",
    "attachments": {
        "nodes": [
            {
                "url": "https://github.com/myorg/myrepo/pull/99",
                "sourceType": "github_pull_request",
            }
        ]
    },
}

LINEAR_ISSUE_NO_PR = {**LINEAR_ISSUE, "attachments": {"nodes": []}}

CHANGED_FILES = [
    {
        "filename": "src/pagination.py",
        "patch": (
            "@@ -10,7 +12,8 @@\n"
            "-def paginate(items, page, size):\n"
            "-    return items[(page-1)*size : page*size + 1]\n"
            "+def paginate(items, page, size):\n"
            "+    return items[(page-1)*size : page*size]\n"
        ),
    }
]

EXISTING_TEST_FILE = """\
def test_paginate_first_page():
    assert paginate([1, 2, 3, 4, 5], 1, 2) == [1, 2]

def test_paginate_last_page():
    assert paginate([1, 2, 3, 4, 5], 3, 2) == [5]
"""

PARSED_TEST_CASES_JSON = """
[
  {"input": "paginate([1, 2, 3, 4, 5], 1, 2)", "expected_output": "[1, 2]"},
  {"input": "paginate([1, 2, 3, 4, 5], 3, 2)", "expected_output": "[5]"}
]
"""

GENERATED_TEST_CASES_JSON = """
[
  {"input": "paginate([1, 2, 3], 1, 2)", "expected_output": "[1, 2]"},
  {"input": "paginate([1, 2, 3], 2, 2)", "expected_output": "[3]"}
]
"""


def _llm_response(text: str):
    m = MagicMock()
    m.response_text = text
    return m


# ---------------------------------------------------------------------------
# Scenario 1: existing test file found → test cases from real tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_challenge_uses_existing_tests(auth_client):
    """Full pipeline: Linear issue → GitHub PR → test file → parsed test cases."""
    with (
        patch("integrations.store.get_integration") as mock_store,
        patch("integrations.linear.get_linear_issue", new_callable=AsyncMock) as mock_issue,
        patch("integrations.github.get_pr_info", new_callable=AsyncMock) as mock_pr,
        patch("integrations.generate.LLM") as MockLLM,
    ):
        # Linear + GitHub both connected
        mock_store.side_effect = lambda uid, provider: (
            "lin_tok" if provider == "linear" else "ghp_tok"
        )
        mock_issue.return_value = LINEAR_ISSUE
        mock_pr.return_value = {
            "changed_files": CHANGED_FILES,
            "test_file_contents": [EXISTING_TEST_FILE],
            "ci_annotations": [],
            "base_source_files": [],
            "head_sha": "abc123",
            "is_merged": False,
        }

        # LLM will be called to parse the test file
        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_llm_response(PARSED_TEST_CASES_JSON))

        resp = await auth_client.post(
            "/api/integrations/generate-challenge",
            json={"issue_id": "ISSUE-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fix off-by-one error in paginate()"
    assert data["source"] == "existing_tests"
    assert len(data["test_cases"]) == 2
    assert data["test_cases"][0]["input"] == "paginate([1, 2, 3, 4, 5], 1, 2)"
    assert data["test_cases"][1]["expected_output"] == "[5]"
    # Starter code stub extracted from diff
    assert "def paginate" in data["starter_code"]


# ---------------------------------------------------------------------------
# Scenario 2: PR found but no test file → LLM generates from diff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_challenge_fallback_to_diff(auth_client):
    """When no test file exists, LLM generates test cases from the PR diff."""
    with (
        patch("integrations.store.get_integration") as mock_store,
        patch("integrations.linear.get_linear_issue", new_callable=AsyncMock) as mock_issue,
        patch("integrations.github.get_pr_info", new_callable=AsyncMock) as mock_pr,
        patch("integrations.generate.LLM") as MockLLM,
    ):
        mock_store.side_effect = lambda uid, provider: (
            "lin_tok" if provider == "linear" else "ghp_tok"
        )
        mock_issue.return_value = LINEAR_ISSUE
        mock_pr.return_value = {
            "changed_files": CHANGED_FILES,
            "test_file_contents": [],
            "ci_annotations": [],
            "base_source_files": [],
            "head_sha": "abc123",
            "is_merged": False,
        }

        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_llm_response(GENERATED_TEST_CASES_JSON))

        resp = await auth_client.post(
            "/api/integrations/generate-challenge",
            json={"issue_id": "ISSUE-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "llm_generated"
    assert len(data["test_cases"]) == 2
    assert "paginate" in data["test_cases"][0]["input"]


# ---------------------------------------------------------------------------
# Scenario 3: GitHub not connected → LLM generates from issue description only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_challenge_no_github_token(auth_client):
    """Without GitHub, falls back to LLM generation from issue description."""
    with (
        patch("integrations.store.get_integration") as mock_store,
        patch("integrations.linear.get_linear_issue", new_callable=AsyncMock) as mock_issue,
        patch("integrations.generate.LLM") as MockLLM,
    ):
        # Only Linear connected, no GitHub
        mock_store.side_effect = lambda uid, provider: (
            "lin_tok" if provider == "linear" else None
        )
        mock_issue.return_value = LINEAR_ISSUE

        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_llm_response(GENERATED_TEST_CASES_JSON))

        resp = await auth_client.post(
            "/api/integrations/generate-challenge",
            json={"issue_id": "ISSUE-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fix off-by-one error in paginate()"
    assert data["source"] == "llm_generated"
    assert len(data["test_cases"]) > 0


# ---------------------------------------------------------------------------
# Scenario 4: Linear issue has no GitHub PR attachment → LLM from description
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_challenge_no_pr_attachment(auth_client):
    """Issue exists but has no linked PR — no files to diff, LLM generates from description."""
    with (
        patch("integrations.store.get_integration") as mock_store,
        patch("integrations.linear.get_linear_issue", new_callable=AsyncMock) as mock_issue,
        patch("integrations.generate.LLM") as MockLLM,
    ):
        mock_store.side_effect = lambda uid, provider: (
            "lin_tok" if provider == "linear" else "ghp_tok"
        )
        mock_issue.return_value = LINEAR_ISSUE_NO_PR

        instance = MockLLM.return_value
        instance.generate = AsyncMock(return_value=_llm_response(GENERATED_TEST_CASES_JSON))

        resp = await auth_client.post(
            "/api/integrations/generate-challenge",
            json={"issue_id": "ISSUE-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "llm_generated"


# ---------------------------------------------------------------------------
# Scenario 5: Linear not connected → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_challenge_linear_not_connected(auth_client):
    """Returns 400 when Linear isn't connected."""
    with patch("integrations.store.get_integration", return_value=None):
        resp = await auth_client.post(
            "/api/integrations/generate-challenge",
            json={"issue_id": "ISSUE-123"},
        )
    assert resp.status_code == 400
    assert "linear not connected" in resp.json()["detail"].lower()
