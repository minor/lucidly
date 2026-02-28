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
async def test_chat_stream_checks_limit_on_later_turns(auth_client: AsyncClient):
    """Turns after the first should ALSO check the daily limit (but not record a new attempt)."""
    mocks = _patch_db()  # count = 0, under limit

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

    # user_turns == 2 → limit IS checked, but attempt is NOT recorded again
    mocks["count_user_challenge_attempts_today"].assert_awaited_once_with(MOCK_USERNAME, "fizzbuzz")
    mocks["record_challenge_attempt"].assert_not_awaited()


@pytest.mark.anyio
async def test_chat_stream_rejects_at_daily_limit_on_later_turns(auth_client: AsyncClient):
    """Even on turn 2+, if the daily limit is reached, 429 is returned."""
    mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=5))

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

    assert resp.status_code == 429
    assert "Daily limit" in resp.json()["detail"]
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


# ---------------------------------------------------------------------------
# Adversarial / abuse scenarios
# ---------------------------------------------------------------------------


class TestAdversarialRateLimit:
    """Adversarial tests for the daily attempt rate-limiting system."""

    @pytest.mark.anyio
    async def test_database_error_fails_closed(self, auth_client: AsyncClient):
        """If the DB count raises an exception, the request must be blocked (503),
        not silently allowed through."""
        mocks = _patch_db(
            count_user_challenge_attempts_today=AsyncMock(side_effect=RuntimeError("DB down"))
        )

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            resp = await auth_client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "hello"}],
                "challenge_id": "fizzbuzz",
            })

        # Must NOT silently proceed — fail closed with 503
        assert resp.status_code == 503
        mocks["record_challenge_attempt"].assert_not_awaited()

    @pytest.mark.anyio
    async def test_repeated_requests_at_limit_all_rejected(self, auth_client: AsyncClient):
        """Sending 5 requests in a row after hitting the limit should all return 429."""
        mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=5))

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            for _ in range(5):
                resp = await auth_client.post("/api/chat/stream", json={
                    "messages": [{"role": "user", "content": "try again"}],
                    "challenge_id": "fizzbuzz",
                })
                assert resp.status_code == 429
                assert "Daily limit" in resp.json()["detail"]

        # No attempt should ever have been recorded
        mocks["record_challenge_attempt"].assert_not_awaited()

    @pytest.mark.anyio
    async def test_limit_enforced_on_every_turn_not_just_first(self, auth_client: AsyncClient):
        """Attacker who previously got through turn 1 and now sends turn 2
        while limit is exhausted must still be blocked."""
        mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=5))

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            resp = await auth_client.post("/api/chat/stream", json={
                "messages": [
                    {"role": "user", "content": "first message"},
                    {"role": "assistant", "content": "first response"},
                    {"role": "user", "content": "second message"},
                ],
                "challenge_id": "fizzbuzz",
            })

        assert resp.status_code == 429
        mocks["record_challenge_attempt"].assert_not_awaited()

    @pytest.mark.anyio
    async def test_limit_at_exact_boundary_count_4_allows(self, auth_client: AsyncClient):
        """count=4 (one below limit) should be allowed and record a new attempt."""
        mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=4))

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            resp = await auth_client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "hello"}],
                "challenge_id": "fizzbuzz",
            })

        # Should NOT be blocked — 4 is under the limit of 5
        assert resp.status_code != 429
        mocks["record_challenge_attempt"].assert_awaited_once_with(MOCK_USERNAME, "fizzbuzz")

    @pytest.mark.anyio
    async def test_later_turns_do_not_inflate_attempt_count(self, auth_client: AsyncClient):
        """Sending 3 turns in a single request should only record one attempt (on turn 1),
        not count each turn as a separate attempt."""
        mocks = _patch_db()  # count=0

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            # Simulate turn 1 (records attempt)
            await auth_client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "turn 1"}],
                "challenge_id": "fizzbuzz",
            })
            # Simulate turn 2 (should NOT record)
            await auth_client.post("/api/chat/stream", json={
                "messages": [
                    {"role": "user", "content": "turn 1"},
                    {"role": "assistant", "content": "response"},
                    {"role": "user", "content": "turn 2"},
                ],
                "challenge_id": "fizzbuzz",
            })

        # record_challenge_attempt should only have been called once (for turn 1)
        assert mocks["record_challenge_attempt"].await_count == 1

    @pytest.mark.anyio
    async def test_omitting_challenge_id_bypasses_limit_check(self, auth_client: AsyncClient):
        """No challenge_id → no limit check. This is expected: free-form chat is unrestricted."""
        mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=99))

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            resp = await auth_client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "hello"}],
                # No challenge_id — limit check must not fire
            })

        mocks["count_user_challenge_attempts_today"].assert_not_awaited()
        assert resp.status_code != 429

    @pytest.mark.anyio
    async def test_unauthenticated_request_blocked_before_limit_check(self, client: AsyncClient):
        """Unauthenticated requests must be rejected with 401 — the limit check
        never runs, but the endpoint is still protected."""
        resp = await client.post("/api/chat/stream", json={
            "messages": [{"role": "user", "content": "hello"}],
            "challenge_id": "fizzbuzz",
        })
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_deeply_nested_conversation_blocked_when_at_limit(self, auth_client: AsyncClient):
        """A long conversation (many turns) sent in a single request is still
        blocked when the user is at the daily limit."""
        mocks = _patch_db(count_user_challenge_attempts_today=AsyncMock(return_value=5))
        # Build a 3-user-turn conversation (within the 4-turn limit)
        messages = []
        for i in range(2):
            messages.append({"role": "user", "content": f"question {i}"})
            messages.append({"role": "assistant", "content": f"answer {i}"})
        messages.append({"role": "user", "content": "final question"})

        with (
            patch("database.get_username_by_auth0_id", mocks["get_username_by_auth0_id"]),
            patch("database.count_user_challenge_attempts_today", mocks["count_user_challenge_attempts_today"]),
            patch("database.record_challenge_attempt", mocks["record_challenge_attempt"]),
        ):
            resp = await auth_client.post("/api/chat/stream", json={
                "messages": messages,
                "challenge_id": "fizzbuzz",
            })

        assert resp.status_code == 429
        assert "Daily limit" in resp.json()["detail"]
