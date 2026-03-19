"""Tests for renamed InterviewChallenge fields."""
from interviews.models import InterviewChallenge, InterviewTurn, AddChallengeRequest
from challenges import TestCase


def test_interview_challenge_uses_test_suite():
    ch = InterviewChallenge(
        id="1", title="T", description="D", category="function",
        test_suite=[TestCase(input="f(1)", expected_output="2")],
    )
    assert ch.test_suite[0].input == "f(1)"
    assert not hasattr(ch, "test_cases")


def test_interview_challenge_category_values():
    for cat in ("function", "UI", "system"):
        ch = InterviewChallenge(id="1", title="T", description="D", category=cat)
        assert ch.category == cat


def test_interview_turn_has_accuracy_at_turn():
    turn = InterviewTurn(turn_number=1, prompt_text="p")
    assert turn.accuracy_at_turn == 0.0
    turn2 = InterviewTurn(turn_number=2, prompt_text="p", accuracy_at_turn=0.75)
    assert turn2.accuracy_at_turn == 0.75


def test_add_challenge_request_uses_test_suite():
    req = AddChallengeRequest(
        title="T", description="D", category="function",
        test_suite=[TestCase(input="f(1)", expected_output="2")],
    )
    assert req.test_suite[0].expected_output == "2"


def test_update_challenge_request_uses_test_suite():
    from interviews.models import UpdateChallengeRequest
    req = UpdateChallengeRequest(
        test_suite=[TestCase(input="g(2)", expected_output="4")],
    )
    assert req.test_suite[0].input == "g(2)"
