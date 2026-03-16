"""Tests for interview mode auto-evaluation after each prompt turn."""
import json
import uuid
import time
from unittest.mock import AsyncMock, MagicMock, patch

from interviews.router import _to_challenge
from interviews.models import (
    InterviewChallenge, InterviewRoom, InterviewConfig, InterviewSession,
)
from challenges import TestCase, Challenge


# ---------------------------------------------------------------------------
# _to_challenge adapter
# ---------------------------------------------------------------------------

def test_to_challenge_maps_function_category():
    ic = InterviewChallenge(
        id="ic1", title="Sort list", description="Sort a list",
        category="function",
        test_suite=[TestCase(input="sort([3,1,2])", expected_output="[1,2,3]")],
    )
    ch = _to_challenge(ic)
    assert isinstance(ch, Challenge)
    assert ch.category == "function"
    assert ch.test_suite[0].input == "sort([3,1,2])"


def test_to_challenge_maps_ui_category():
    ic = InterviewChallenge(
        id="ic2", title="Button", description="Make a button",
        category="UI",
    )
    ch = _to_challenge(ic)
    assert ch.category == "UI"


def test_to_challenge_maps_system_category():
    ic = InterviewChallenge(
        id="ic3", title="Design", description="System design",
        category="system",
    )
    ch = _to_challenge(ic)
    assert ch.category == "system"


def test_to_challenge_preserves_starter_code():
    ic = InterviewChallenge(
        id="ic4", title="T", description="D", category="function",
        starter_code="def foo(): pass",
    )
    ch = _to_challenge(ic)
    assert ch.starter_code == "def foo(): pass"


def test_to_challenge_none_test_suite():
    ic = InterviewChallenge(id="ic5", title="T", description="D", category="function")
    ch = _to_challenge(ic)
    assert ch.test_suite is None


# ---------------------------------------------------------------------------
# Auto-eval in submit_prompt SSE stream
# ---------------------------------------------------------------------------

async def test_submit_prompt_includes_accuracy_in_done_event(auth_client):
    """The SSE done event should carry accuracy and test_results after auto-eval."""
    room_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    challenge_id = str(uuid.uuid4())

    challenge = InterviewChallenge(
        id=challenge_id,
        title="Add numbers",
        description="Return sum",
        category="function",
        test_suite=[TestCase(input="add(1, 2)", expected_output="3")],
    )
    room = InterviewRoom(
        id=room_id, created_by="x", title="T", invite_code="ABCD1234",
        config=InterviewConfig(), challenges=[challenge], status="active",
    )
    session = InterviewSession(
        id=session_id, room_id=room_id, challenge_id=challenge_id,
        candidate_name="Alice", status="active", started_at=time.time(),
    )

    mock_eval_result = MagicMock()
    mock_eval_result.accuracy = 1.0
    mock_eval_result.test_results = [True]
    mock_eval_result.details = {"source": "local"}
    mock_eval_result.execution_output = None

    with (
        patch("interviews.router.store.get_session", return_value=session),
        patch("interviews.router.store.get_room", return_value=room),
        patch("interviews.router.store.add_turn", return_value=session),
        patch("interviews.router.store.update_session_accuracy"),
        patch("interviews.router.realtime.broadcast", new_callable=AsyncMock),
        patch("interviews.router._evaluator.evaluate", new_callable=AsyncMock, return_value=mock_eval_result),
        patch("interviews.router.LLM") as MockLLM,
    ):
        instance = MockLLM.return_value
        async def fake_stream(*args, **kwargs):
            yield "```python\ndef add(a, b): return a + b\n```"
        instance.stream = fake_stream
        MockLLM.extract_code_blocks = MagicMock(return_value="def add(a, b): return a + b")

        resp = await auth_client.post(
            f"/api/interviews/{room_id}/sessions/{session_id}/prompt",
            json={"prompt": "write add function"},
        )

    assert resp.status_code == 200
    done_event = None
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if data.get("type") == "done":
                done_event = data
                break

    assert done_event is not None
    assert done_event["accuracy"] == 1.0
    assert done_event["test_results"] == [True]
