"""Tests for the daily-attempts tracking feature.

Covers:
  - GET /api/challenges/daily-attempts endpoint
  - Daily attempt limit enforcement on first turn of /api/chat/stream
  - Attempt recording on first turn
  - Auth gating on daily-attempts endpoint
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from main import app
from auth import get_current_user
from tests.conftest import MOCK_USER_ID


MOCK_USERNAME = "testplayer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mock_current_user() -> str:
    return MOCK_USER_ID


def _patch_db(**overrides):
    """Return a dict of mock patches for database functions used by daily-attempts.

    Defaults:
      - get_username_by_auth0_id → MOCK_USERNAME
      - count_user_attempts_today_bulk → {}
      - count_user_challenge_attempts_today → 0
      - record_challenge_attempt → None
    """
    defaults = {
        "get_username_by_auth0_id": AsyncMock(return_value=MOCK_USERNAME),
        "count_user_attempts_today_bulk": AsyncMock(return_value={}),
        "count_user_challenge_attempts_today": AsyncMock(return_value=0),
        "record_challenge_attempt": AsyncMock(return_value=None),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# GET /api/challenges/daily-attempts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_daily_attempts_requires_auth(client: AsyncClient):
    """Unauthenticated request should return 401."""
    resp = await client.get("/api/challenges/daily-attempts")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_daily_attempts_returns_empty_when_no_username(auth_client: AsyncClient):
    """If the user has no username set, return an empty dict."""
    with patch("database.get_username_by_auth0_id", new_callable=AsyncMock, return_value=None):
        resp = await auth_client.get("/api/challenges/daily-attempts")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.anyio
async def test_daily_attempts_returns_counts(auth_client: AsyncClient):
    """Should return the bulk attempt counts from the database."""
    mock_counts = {"fizzbuzz": 3, "two-sum": 1}
    mocks = _patch_db(count_user_attempts_today_bulk=AsyncMock(return_value=mock_counts))

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_attempts_today_bulk", mocks["count_user_attempts_today_bulk"]),
    ):
        resp = await auth_client.get("/api/challenges/daily-attempts")

    assert resp.status_code == 200
    assert resp.json() == mock_counts
    mocks["count_user_attempts_today_bulk"].assert_awaited_once_with(MOCK_USERNAME)


@pytest.mark.anyio
async def test_daily_attempts_returns_empty_when_none_used(auth_client: AsyncClient):
    """If the user has no attempts today, return an empty dict."""
    mocks = _patch_db()

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_attempts_today_bulk", mocks["count_user_attempts_today_bulk"]),
    ):
        resp = await auth_client.get("/api/challenges/daily-attempts")

    assert resp.status_code == 200
    assert resp.json() == {}


# ---------------------------------------------------------------------------
# /api/chat/stream — daily attempt limit enforcement
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_chat_stream_records_attempt_on_first_turn(auth_client: AsyncClient):
    """First turn with a challenge_id should record an attempt."""
    mocks = _patch_db()

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
        patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
    ):
        resp = await auth_client.post("/api/chat/stream", json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "fizzbuzz",
        })

    # The request will proceed past the limit check (count=0 < 5).
    # It may fail later (no real LLM), but that's fine — we're testing
    # that record_challenge_attempt was called.
    mocks["record_challenge_attempt"].assert_awaited_once_with(MOCK_USERNAME, "fizzbuzz")


@pytest.mark.anyio
async def test_chat_stream_rejects_at_daily_limit(auth_client: AsyncClient):
    """When 5 attempts already used today, first turn should return 429."""
    mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=5))

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
        patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
    ):
        resp = await auth_client.post("/api/chat/stream", json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "fizzbuzz",
        })

    assert resp.status_code == 429
    assert "Daily limit" in resp.json()["detail"]
    mocks["record_challenge_attempt"].assert_not_awaited()


@pytest.mark.anyio
async def test_chat_stream_skips_limit_check_on_later_turns(auth_client: AsyncClient):
    """Turns after the first should not check or record daily attempts."""
    mocks = _patch_db()

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
        patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
    ):
        resp = await auth_client.post("/api/chat/stream", json={
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
                {"role": "user", "content": "write fizzbuzz"},
            ],
            "challenge_id": "fizzbuzz",
        })

    # user_turns == 2, so the daily limit check block (user_turns == 1) is skipped
    mocks["count_user_challenge_attempts_today"].assert_not_awaited()
    mocks["record_challenge_attempt"].assert_not_awaited()


@pytest.mark.anyio
async def test_chat_stream_skips_limit_check_without_challenge_id(auth_client: AsyncClient):
    """When no challenge_id is provided, daily limit check is skipped."""
    mocks = _patch_db()

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
        patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
    ):
        resp = await auth_client.post("/api/chat/stream", json={
            "messages": [{"role": "user", "content": "hello"}],
        })

    mocks["count_user_challenge_attempts_today"].assert_not_awaited()
    mocks["record_challenge_attempt"].assert_not_awaited()


@pytest.mark.anyio
async def test_chat_stream_no_username_skips_limit(auth_client: AsyncClient):
    """If the user has no username, skip the daily limit check entirely."""
    mocks = _patch_db(get_username_by_auth0_id=AsyncMock(return_value=None))

    with (
        patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
        patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
        patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
    ):
        resp = await auth_client.post("/api/chat/stream", json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "fizzbuzz",
        })

    mocks["count_user_challenge_attempts_today"].assert_not_awaited()
    mocks["record_challenge_attempt"].assert_not_awaited()
