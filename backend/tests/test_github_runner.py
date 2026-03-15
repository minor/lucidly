"""
Unit tests for github_runner _impl functions.
All external calls (httpx, subprocess) are mocked.
Tests call _impl functions directly — no Modal deployment needed.
"""
import json
import tarfile
import tempfile
import io
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from integrations.github_runner import (
    _fetch_and_prepare_impl,
    _run_pytest_impl,
    _discover_pr_fixed_tests_impl,
    _run_tests_impl,
)


# ---------------------------------------------------------------------------
# Helpers to build a fake tarball in memory
# ---------------------------------------------------------------------------

def _make_tarball(files: dict[str, str]) -> bytes:
    """Create an in-memory tarball with a 'myrepo-abc123/' root dir."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel_path, content in files.items():
            full_path = f"myrepo-abc123/{rel_path}"
            data = content.encode()
            info = tarfile.TarInfo(name=full_path)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _fetch_and_prepare_impl
# ---------------------------------------------------------------------------

def _mock_httpx_response(content: bytes):
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_and_prepare_writes_test_files(tmp_path, monkeypatch):
    """Verifies tarball extracted and test files written to correct paths."""
    tarball = _make_tarball({"src/parser.py": "def tokenize(s): pass"})
    mock_resp = _mock_httpx_response(tarball)

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=mock_resp)
        mock_cls.return_value = mc

        test_files = [{"path": "tests/test_parser.py", "content": "def test_foo(): pass"}]
        repo_root = _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", test_files)

    assert (repo_root / "tests" / "test_parser.py").read_text() == "def test_foo(): pass"
    assert (repo_root / "src" / "parser.py").read_text() == "def tokenize(s): pass"


def test_fetch_and_prepare_installs_requirements(tmp_path):
    """pip install runs if requirements.txt is in the tarball."""
    tarball = _make_tarball({"requirements.txt": "pytest\n"})
    mock_resp = _mock_httpx_response(tarball)

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=mock_resp)
        mock_cls.return_value = mc

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            repo_root = _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", [])

    assert any("pip" in str(c) for c in mock_run.call_args_list[0][0][0])


def test_fetch_and_prepare_no_requirements_no_pip_call():
    tarball = _make_tarball({"src/parser.py": "pass"})
    mock_resp = _mock_httpx_response(tarball)

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=mock_resp)
        mock_cls.return_value = mc

        with patch("subprocess.run") as mock_run:
            _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", [])

    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# _run_pytest_impl
# ---------------------------------------------------------------------------

def _make_pytest_report(tests: list[dict]) -> str:
    return json.dumps({"tests": tests})


def test_run_pytest_returns_test_list(tmp_path):
    report_content = _make_pytest_report([
        {"nodeid": "tests/test_parser.py::test_tok", "outcome": "passed"},
        {"nodeid": "tests/test_parser.py::test_bad", "outcome": "failed"},
    ])
    report_file = tmp_path / "report.json"
    report_file.write_text(report_content)

    proc = MagicMock(stdout="", stderr="", returncode=1)

    with patch("subprocess.run", return_value=proc):
        with patch("tempfile.mktemp", return_value=str(report_file)):
            result = _run_pytest_impl(tmp_path)

    assert len(result) == 2
    assert result[0]["outcome"] == "passed"
    assert result[1]["outcome"] == "failed"


def test_run_pytest_missing_report_returns_empty(tmp_path):
    """If report file not written (e.g. crash), return empty list."""
    proc = MagicMock(stdout="", stderr="crash", returncode=2)

    with patch("subprocess.run", return_value=proc):
        with patch("tempfile.mktemp", return_value=str(tmp_path / "nonexistent.json")):
            result = _run_pytest_impl(tmp_path)

    assert result == []


def test_run_pytest_with_test_ids(tmp_path):
    """Test IDs are passed as positional args to pytest."""
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps({"tests": []}))
    proc = MagicMock(stdout="", stderr="", returncode=0)

    with patch("subprocess.run", return_value=proc) as mock_run:
        with patch("tempfile.mktemp", return_value=str(report_file)):
            _run_pytest_impl(tmp_path, test_ids=["tests/test_foo.py::test_bar"])

    cmd = mock_run.call_args[0][0]
    assert "tests/test_foo.py::test_bar" in cmd


# ---------------------------------------------------------------------------
# _discover_pr_fixed_tests_impl
# ---------------------------------------------------------------------------

def _fake_fetch(token, owner, repo, sha, test_files):
    """Returns a tmp_path-like Path with a fake requirements.txt."""
    import tempfile
    p = Path(tempfile.mkdtemp())
    return p


def test_discover_pr_fixed_tests_impl_basic():
    """Tests failing at base + passing at head are returned as fixed."""
    base_results = [
        {"nodeid": "tests/test_foo.py::test_a", "outcome": "failed"},
        {"nodeid": "tests/test_foo.py::test_b", "outcome": "passed"},
    ]
    head_results = [
        {"nodeid": "tests/test_foo.py::test_a", "outcome": "passed"},
        {"nodeid": "tests/test_foo.py::test_b", "outcome": "passed"},
    ]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_fetch:
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_fetch.return_value = Path("/tmp/fake")
            mock_pytest.side_effect = [base_results, head_results]

            fixed = _discover_pr_fixed_tests_impl(
                "tok", "owner", "repo", "base_sha", "head_sha",
                [{"path": "tests/test_foo.py", "content": "..."}]
            )

    assert fixed == ["tests/test_foo.py::test_a"]


def test_discover_pr_fixed_tests_impl_no_fixed():
    """Returns empty list when no tests go failing→passing."""
    base_results = [{"nodeid": "tests/test_foo.py::test_a", "outcome": "passed"}]
    head_results = [{"nodeid": "tests/test_foo.py::test_a", "outcome": "passed"}]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_fetch:
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_fetch.return_value = Path("/tmp/fake")
            mock_pytest.side_effect = [base_results, head_results]

            fixed = _discover_pr_fixed_tests_impl(
                "tok", "owner", "repo", "base_sha", "head_sha", []
            )

    assert fixed == []


# ---------------------------------------------------------------------------
# _run_tests_impl
# ---------------------------------------------------------------------------

def test_run_tests_impl_injects_and_runs(tmp_path):
    """Solution code replaces target file content, then pytest runs on fixed tests."""
    source_file = tmp_path / "src" / "parser.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("def tokenize(s): return []")

    solution = "def tokenize(s): return s.split()"
    test_ids = ["tests/test_parser.py::test_tok"]

    pytest_results = [{"nodeid": "tests/test_parser.py::test_tok", "outcome": "passed"}]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_fetch:
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_fetch.return_value = tmp_path
            mock_pytest.return_value = pytest_results

            result = _run_tests_impl(
                "tok", "owner", "repo", "base_sha",
                [{"path": "tests/test_parser.py", "content": "..."}],
                "src/parser.py", solution, test_ids
            )

    assert source_file.read_text() == solution
    assert result == pytest_results
    mock_pytest.assert_called_once_with(tmp_path, test_ids=test_ids)


def test_run_tests_impl_source_file_unparseable(tmp_path):
    """If solution code is not valid Python, raises SyntaxError before running tests."""
    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_fetch:
        mock_fetch.return_value = tmp_path

        with pytest.raises(SyntaxError):
            _run_tests_impl(
                "tok", "owner", "repo", "base_sha",
                [],
                "src/parser.py", "def broken(: pass", []
            )
