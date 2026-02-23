"""Tests that verify slowapi rate limits fire correctly on each rate-limited endpoint."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _exhaust_rate_limit(
    client: AsyncClient,
    method: str,
    url: str,
    limit: int,
    *,
    json: dict | None = None,
):
    """Send *limit* requests that must NOT be 429, then one more that MUST be 429."""
    for i in range(limit):
        resp = await getattr(client, method)(url, json=json)
        assert resp.status_code != 429, (
            f"Request {i + 1}/{limit} was unexpectedly rate-limited"
        )

    final = await getattr(client, method)(url, json=json)
    assert final.status_code == 429, (
        f"Request {limit + 1} should have been rate-limited but got {final.status_code}"
    )


# ---------------------------------------------------------------------------
# Low-limit endpoints (exhaustive)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_prompt_feedback_rate_limit(auth_client: AsyncClient):
    """/api/prompt-feedback — 2/minute"""
    await _exhaust_rate_limit(
        auth_client,
        "post",
        "/api/prompt-feedback",
        limit=2,
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "nonexistent",
        },
    )


@pytest.mark.anyio
async def test_evaluate_ui_rate_limit(auth_client: AsyncClient):
    """/api/evaluate-ui — 3/minute"""
    await _exhaust_rate_limit(
        auth_client,
        "post",
        "/api/evaluate-ui",
        limit=3,
        json={"challenge_id": "nonexistent", "generated_html": "<p>test</p>"},
    )


@pytest.mark.anyio
async def test_generate_tests_rate_limit(auth_client: AsyncClient):
    """/api/challenges/{id}/generate-tests — 5/minute"""
    await _exhaust_rate_limit(
        auth_client,
        "post",
        "/api/challenges/nonexistent/generate-tests",
        limit=5,
    )


@pytest.mark.anyio
async def test_calculate_score_rate_limit(auth_client: AsyncClient):
    """/api/calculate-score — 10/minute"""
    await _exhaust_rate_limit(
        auth_client,
        "post",
        "/api/calculate-score",
        limit=10,
        json={
            "challenge_id": "nonexistent",
            "accuracy": 0.5,
            "elapsed_sec": 10.0,
            "total_tokens": 100,
            "total_turns": 1,
        },
    )


# ---------------------------------------------------------------------------
# Higher-limit endpoints (exhaustive — requests are fast because they fail
# on missing resources before making any external calls)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_session_prompt_rate_limit(client: AsyncClient):
    """/api/sessions/{id}/prompt — 20/minute (no auth required)"""
    await _exhaust_rate_limit(
        client,
        "post",
        "/api/sessions/nonexistent/prompt",
        limit=20,
        json={"prompt": "test"},
    )


@pytest.mark.anyio
async def test_interview_prompt_rate_limit(client: AsyncClient):
    """/api/interviews/{room}/sessions/{session}/prompt — 20/minute"""
    await _exhaust_rate_limit(
        client,
        "post",
        "/api/interviews/fakeroom/sessions/fakesession/prompt",
        limit=20,
        json={"prompt": "test"},
    )


@pytest.mark.anyio
async def test_chat_stream_rate_limit(auth_client: AsyncClient):
    """/api/chat/stream — 30/minute"""
    await _exhaust_rate_limit(
        auth_client,
        "post",
        "/api/chat/stream",
        limit=30,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
