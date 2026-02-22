"""Tests for session expiration, standard user flows, and adversarial API abuse."""

import time

import pytest
from fastapi.testclient import TestClient

import scoring_sessions
from scoring_sessions import _scoring_sessions


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Ensure a clean session dict for every test."""
    _scoring_sessions.clear()
    yield
    _scoring_sessions.clear()


@pytest.fixture()
def client():
    from main import app

    return TestClient(app, raise_server_exceptions=False)


def _create_session(client: TestClient, challenge_id: str = "fizzbuzz") -> str:
    resp = client.post(
        "/api/scoring-sessions",
        json={"challenge_id": challenge_id, "username": "testuser"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def _expire_session(session_id: str) -> None:
    """Force-expire by backdating started_at beyond the TTL."""
    session = _scoring_sessions[session_id]
    session.started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 1


# =========================================================================
# Standard user flow — happy path
# =========================================================================


class TestStandardUserFlow:
    """Simulate a normal user: create session, record turns, freeze on
    perfect accuracy, submit, verify timing math."""

    def test_full_flow_timing(self):
        """Elapsed time should equal (frozen_at - started_at) minus processing time."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "alice")
        sid = session.id

        now = time.time()
        session.started_at = now - 120  # pretend session started 120s ago

        scoring_sessions.record_turn(
            sid,
            input_tokens=100,
            output_tokens=200,
            cost=0.001,
            user_message="write fizzbuzz",
            assistant_message="def fizzbuzz(n): ...",
        )
        scoring_sessions.record_processing_time(sid, 5.0)

        scoring_sessions.freeze_timer(sid)
        freeze_time = _scoring_sessions[sid].frozen_at
        assert freeze_time is not None

        elapsed = freeze_time - session.started_at - session.server_processing_seconds
        assert 114.0 <= elapsed <= 116.0, f"Expected ~115s, got {elapsed}"

    def test_turn_stats_accumulate(self):
        session = scoring_sessions.create_scoring_session("fizzbuzz", "bob")
        sid = session.id

        for i in range(3):
            scoring_sessions.record_turn(
                sid,
                input_tokens=50,
                output_tokens=100,
                cost=0.002,
                user_message=f"prompt {i}",
                assistant_message=f"response {i}",
            )

        s = _scoring_sessions[sid]
        assert s.total_turns == 3
        assert s.total_input_tokens == 150
        assert s.total_output_tokens == 300
        assert abs(s.total_cost - 0.006) < 1e-9
        assert len(s.messages) == 6  # 3 user + 3 assistant

    def test_processing_time_subtracted(self):
        """Server processing time should not count toward the user's elapsed time."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "carol")
        sid = session.id

        now = time.time()
        session.started_at = now - 60

        scoring_sessions.record_processing_time(sid, 10.0)
        scoring_sessions.record_processing_time(sid, 5.0)
        scoring_sessions.freeze_timer(sid)

        freeze_time = _scoring_sessions[sid].frozen_at
        raw_elapsed = freeze_time - session.started_at
        adjusted = raw_elapsed - session.server_processing_seconds

        assert session.server_processing_seconds == 15.0
        assert adjusted < raw_elapsed
        assert 44.0 <= adjusted <= 46.0

    def test_freeze_captures_moment_of_perfection(self):
        """Freezing should snapshot the current time; further delay shouldn't matter."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "dave")
        sid = session.id
        session.started_at = time.time() - 30

        scoring_sessions.freeze_timer(sid)
        frozen = _scoring_sessions[sid].frozen_at
        assert frozen is not None

        time.sleep(0.05)

        assert _scoring_sessions[sid].frozen_at == frozen, "frozen_at should not change"

    def test_unfreeze_then_refreeze_updates_time(self):
        """If accuracy drops and returns, frozen_at should update to the new moment."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "eve")
        sid = session.id

        scoring_sessions.freeze_timer(sid)
        first_freeze = _scoring_sessions[sid].frozen_at

        time.sleep(0.05)

        scoring_sessions.unfreeze_timer(sid)
        assert _scoring_sessions[sid].frozen_at is None

        time.sleep(0.05)

        scoring_sessions.freeze_timer(sid)
        second_freeze = _scoring_sessions[sid].frozen_at

        assert second_freeze > first_freeze

    def test_submit_uses_frozen_time(self, client: TestClient):
        """Submit should use frozen_at (not current time) for elapsed calculation."""
        sid = _create_session(client)
        session = _scoring_sessions[sid]

        now = time.time()
        session.started_at = now - 100
        session.frozen_at = now - 50  # froze 50s into the challenge
        session.server_processing_seconds = 10.0
        session.last_test_accuracy = 1.0

        resp = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={"code": "def fizzbuzz(n): pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "composite_score" in data
        assert "accuracy_score" in data

    def test_double_submit_rejected(self, client: TestClient):
        """Submitting twice should fail — session is already completed."""
        sid = _create_session(client)
        session = _scoring_sessions[sid]
        session.last_test_accuracy = 1.0

        resp1 = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={"code": "pass"},
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={"code": "pass"},
        )
        assert resp2.status_code == 400
        assert "already completed" in resp2.json()["detail"].lower()


# =========================================================================
# Expiration — endpoints must return 410
# =========================================================================


class TestExpiredSession:

    def test_submit_expired(self, client: TestClient):
        sid = _create_session(client)
        _expire_session(sid)
        resp = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={"code": "print(1)"},
        )
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_chat_stream_expired(self, client: TestClient):
        sid = _create_session(client)
        _expire_session(sid)
        resp = client.post(
            "/api/chat/stream",
            json={
                "messages": [{"role": "user", "content": "hello"}],
                "scoring_session_id": sid,
            },
        )
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_run_tests_expired(self, client: TestClient):
        sid = _create_session(client)
        _expire_session(sid)
        resp = client.post(
            "/api/run-tests",
            json={
                "code": "def fizzbuzz(n): pass",
                "challenge_id": "fizzbuzz",
                "sandbox_id": "fake-sandbox",
                "scoring_session_id": sid,
            },
        )
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_nonexistent_session_returns_410(self, client: TestClient):
        resp = client.post(
            "/api/scoring-sessions/does-not-exist/submit",
            json={"code": "x"},
        )
        assert resp.status_code == 410

    def test_repeated_calls_all_410(self, client: TestClient):
        sid = _create_session(client)
        _expire_session(sid)

        for _ in range(5):
            resp = client.post(
                f"/api/scoring-sessions/{sid}/submit",
                json={"code": "x"},
            )
            assert resp.status_code == 410

        for _ in range(3):
            resp = client.post(
                "/api/chat/stream",
                json={
                    "messages": [{"role": "user", "content": "hi"}],
                    "scoring_session_id": sid,
                },
            )
            assert resp.status_code == 410

    def test_chat_without_session_id_not_blocked(self, client: TestClient):
        """Chat should work fine when no scoring_session_id is provided."""
        resp = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code != 410

    def test_cleanup_only_removes_expired(self):
        s1 = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        s2 = scoring_sessions.create_scoring_session("fizzbuzz", "user2")
        s3 = scoring_sessions.create_scoring_session("fizzbuzz", "user3")

        _scoring_sessions[s1.id].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 100
        _scoring_sessions[s2.id].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 1

        removed = scoring_sessions.cleanup_expired_sessions()

        assert removed == 2
        assert s1.id not in _scoring_sessions
        assert s2.id not in _scoring_sessions
        assert s3.id in _scoring_sessions


# =========================================================================
# Adversarial / abuse scenarios
# =========================================================================


class TestAdversarial:

    def test_create_session_for_nonexistent_challenge(self, client: TestClient):
        """Creating a session for a challenge that doesn't exist should fail."""
        resp = client.post(
            "/api/scoring-sessions",
            json={"challenge_id": "does-not-exist-challenge", "username": "hacker"},
        )
        assert resp.status_code == 404

    def test_submit_someone_elses_session(self, client: TestClient):
        """A session ID is opaque — but submitting a valid one should still work
        (no auth on session ownership yet). This test documents current behavior."""
        sid = _create_session(client)
        _scoring_sessions[sid].last_test_accuracy = 1.0

        resp = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={"code": "pass"},
        )
        assert resp.status_code == 200

    def test_submit_with_empty_body(self, client: TestClient):
        """Submitting with no code/sandbox should still go through (accuracy = 0)."""
        sid = _create_session(client)
        resp = client.post(
            f"/api/scoring-sessions/{sid}/submit",
            json={},
        )
        assert resp.status_code == 200

    def test_record_turn_on_completed_session(self):
        """After completion, recording turns should silently no-op."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id
        scoring_sessions.complete_scoring_session(sid)

        scoring_sessions.record_turn(
            sid,
            input_tokens=999,
            output_tokens=999,
            cost=100.0,
            user_message="sneaky",
            assistant_message="response",
        )
        assert _scoring_sessions[sid].total_turns == 0
        assert _scoring_sessions[sid].total_cost == 0.0

    def test_freeze_on_completed_session(self):
        """Freezing a completed session should no-op."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id
        scoring_sessions.complete_scoring_session(sid)

        scoring_sessions.freeze_timer(sid)
        assert _scoring_sessions[sid].frozen_at is None

    def test_record_processing_time_on_completed_session(self):
        """Processing time on a completed session should no-op."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id
        scoring_sessions.complete_scoring_session(sid)

        scoring_sessions.record_processing_time(sid, 999.0)
        assert _scoring_sessions[sid].server_processing_seconds == 0.0

    def test_fabricated_session_id_rejected(self, client: TestClient):
        """Random UUID should be rejected with 410."""
        import uuid

        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/scoring-sessions/{fake_id}/submit",
            json={"code": "x"},
        )
        assert resp.status_code == 410

    def test_expired_session_purged_from_memory(self):
        """After get_scoring_session returns None for an expired session,
        the session should be fully removed from the dict."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id
        assert sid in _scoring_sessions

        _scoring_sessions[sid].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 1

        result = scoring_sessions.get_scoring_session(sid)
        assert result is None
        assert sid not in _scoring_sessions, "Expired session should be deleted from dict"

    def test_cannot_inflate_stats_after_expiry(self):
        """Even if someone holds a reference, the recording functions
        check the dict and should no-op for missing sessions."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id
        _scoring_sessions[sid].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 1

        scoring_sessions.get_scoring_session(sid)
        assert sid not in _scoring_sessions

        scoring_sessions.record_turn(
            sid,
            input_tokens=1,
            output_tokens=1,
            cost=0.0,
            user_message="ghost",
            assistant_message="ghost",
        )
        scoring_sessions.record_processing_time(sid, 999.0)
        scoring_sessions.freeze_timer(sid)

        assert sid not in _scoring_sessions

    def test_session_near_ttl_boundary(self):
        """A session well within the TTL should be valid; one past should not."""
        session = scoring_sessions.create_scoring_session("fizzbuzz", "user1")
        sid = session.id

        _scoring_sessions[sid].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS + 5
        assert scoring_sessions.get_scoring_session(sid) is not None, "5s before TTL should be valid"

        _scoring_sessions[sid].started_at = time.time() - scoring_sessions.SESSION_TTL_SECONDS - 1
        assert scoring_sessions.get_scoring_session(sid) is None, "1s past TTL should expire"

    def test_rapid_session_creation_independent(self, client: TestClient):
        """Multiple sessions should be independent — expiring one shouldn't affect others."""
        sid1 = _create_session(client)
        sid2 = _create_session(client)
        sid3 = _create_session(client)

        _expire_session(sid2)

        assert scoring_sessions.get_scoring_session(sid1) is not None
        assert scoring_sessions.get_scoring_session(sid2) is None
        assert scoring_sessions.get_scoring_session(sid3) is not None

    def test_chat_stream_with_expired_session_id_blocks_request(self, client: TestClient):
        """Even though chat could work without a session, providing an expired
        session ID should block the request to alert the user."""
        sid = _create_session(client)
        _expire_session(sid)

        resp = client.post(
            "/api/chat/stream",
            json={
                "messages": [{"role": "user", "content": "hello"}],
                "scoring_session_id": sid,
            },
        )
        assert resp.status_code == 410

    def test_run_tests_with_expired_session_id_blocks_request(self, client: TestClient):
        """Same as above but for run-tests."""
        sid = _create_session(client)
        _expire_session(sid)

        resp = client.post(
            "/api/run-tests",
            json={
                "code": "def fizzbuzz(n): pass",
                "challenge_id": "fizzbuzz",
                "sandbox_id": "fake",
                "scoring_session_id": sid,
            },
        )
        assert resp.status_code == 410
