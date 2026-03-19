"""Tests for Challenge and RepoContext Pydantic models."""
import pytest
from challenges import Challenge, RepoContext


def test_repo_context_model():
    rc = RepoContext(
        owner="acme",
        repo="myrepo",
        base_sha="abc123",
        file_paths=["src/parser.py"],
        challenge_test_ids=["tests/test_parser.py::test_tokenize"],
    )
    assert rc.owner == "acme"
    assert rc.challenge_test_ids == ["tests/test_parser.py::test_tokenize"]


def test_challenge_has_repo_context_field():
    c = Challenge(
        id="c1",
        title="Fix parser",
        description="desc",
        category="function",
        difficulty="medium",
        user_id="user|123",
        repo_context=RepoContext(
            owner="acme", repo="myrepo", base_sha="abc",
            file_paths=["src/parser.py"], challenge_test_ids=[],
        ),
        test_files=[{"path": "tests/test_parser.py", "content": "def test_foo(): pass"}],
    )
    assert c.user_id == "user|123"
    assert c.repo_context is not None
    assert c.repo_context.file_paths == ["src/parser.py"]
    assert c.test_files[0]["path"] == "tests/test_parser.py"


def test_challenge_defaults():
    """New fields default to None / empty list."""
    c = Challenge(
        id="c2", title="t", description="d",
        category="function", difficulty="easy",
    )
    assert c.user_id is None
    assert c.repo_context is None
    assert c.test_files == []
