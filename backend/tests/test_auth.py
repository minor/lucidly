"""Tests that verify authentication gates on protected endpoints.

Each test sends an unauthenticated request (no dependency override) and asserts
a 401 response, then activates the get_current_user override and asserts a
non-401 response.
"""

import pytest
from httpx import AsyncClient

from main import app
from auth import get_current_user
from tests.conftest import MOCK_USER_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mock_current_user() -> str:
    return MOCK_USER_ID


async def _assert_requires_auth(
    client: AsyncClient,
    method: str,
    url: str,
    *,
    json: dict | None = None,
):
    """Verify endpoint returns 401 without auth and non-401 with auth."""
    app.dependency_overrides.pop(get_current_user, None)

    resp_no_auth = await getattr(client, method)(url, json=json)
    assert resp_no_auth.status_code == 401, (
        f"Expected 401 without auth, got {resp_no_auth.status_code} on {method.upper()} {url}"
    )

    app.dependency_overrides[get_current_user] = _mock_current_user
    resp_auth = await getattr(client, method)(url, json=json)
    assert resp_auth.status_code != 401, (
        f"Authenticated request should not return 401 on {method.upper()} {url}"
    )


# ---------------------------------------------------------------------------
# Auth-gated endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_tests_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/challenges/nonexistent/generate-tests",
    )


@pytest.mark.anyio
async def test_create_username_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/username",
        json={"auth0_id": MOCK_USER_ID, "username": "testuser"},
    )


@pytest.mark.anyio
async def test_calculate_score_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/calculate-score",
        json={
            "challenge_id": "nonexistent",
            "accuracy": 0.5,
            "elapsed_sec": 10.0,
            "total_tokens": 100,
            "total_turns": 1,
        },
    )


@pytest.mark.anyio
async def test_agent_runs_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/agent-runs",
        json={"agent_id": "nonexistent", "challenge_id": "nonexistent"},
    )


@pytest.mark.anyio
async def test_chat_stream_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/chat/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )


@pytest.mark.anyio
async def test_sandbox_create_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/sandbox/create",
    )


@pytest.mark.anyio
async def test_sandbox_terminate_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/sandbox/fake-id/terminate",
    )


@pytest.mark.anyio
async def test_run_tests_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/run-tests",
        json={"code": "print(1)", "challenge_id": "nonexistent", "sandbox_id": "fake"},
    )


@pytest.mark.anyio
async def test_evaluate_ui_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/evaluate-ui",
        json={"challenge_id": "nonexistent", "generated_html": "<p>test</p>"},
    )


@pytest.mark.anyio
async def test_run_code_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/run-code",
        json={"sandbox_id": "fake", "code": "print(1)"},
    )


@pytest.mark.anyio
async def test_prompt_feedback_requires_auth(client: AsyncClient):
    await _assert_requires_auth(
        client, "post",
        "/api/prompt-feedback",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "nonexistent",
        },
    )
