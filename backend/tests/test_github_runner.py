"""
Unit tests for github_runner _impl functions.
All external calls (httpx, subprocess) are mocked.
Tests call _impl functions directly — no Modal deployment needed.
"""
import io
import json
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations.github_runner import (
    _fetch_and_prepare_impl,
    _run_pytest_impl,
    _discover_pr_fixed_tests_impl,
    _run_tests_impl,
)


# ---------------------------------------------------------------------------
# Helpers
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


def _make_pytest_report(tests: list[dict]) -> str:
    return json.dumps({"tests": tests})


def _prep_repo(tmp_path, source_content: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "parser.py").write_text(source_content)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_tok(): pass")
    return tmp_path


# ---------------------------------------------------------------------------
# _fetch_and_prepare_impl
# ---------------------------------------------------------------------------

def _mock_httpx_response(content: bytes):
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_and_prepare_writes_test_files(tmp_path):
    """Verifies tarball extracted and test files written to correct paths."""
    tarball = _make_tarball({"src/parser.py": "def tokenize(s): pass"})

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=_mock_httpx_response(tarball))
        mock_cls.return_value = mc

        test_files = [{"path": "tests/test_parser.py", "content": "def test_foo(): pass"}]
        repo_root = _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", test_files)

    assert (repo_root / "tests" / "test_parser.py").read_text() == "def test_foo(): pass"
    assert (repo_root / "src" / "parser.py").read_text() == "def tokenize(s): pass"


def test_fetch_and_prepare_installs_requirements():
    """pip install runs if requirements.txt is in the tarball."""
    tarball = _make_tarball({"requirements.txt": "pytest\n"})

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=_mock_httpx_response(tarball))
        mock_cls.return_value = mc

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", [])

    assert any("pip" in str(c) for c in mock_run.call_args_list[0][0][0])


def test_fetch_and_prepare_no_requirements_no_pip_call():
    tarball = _make_tarball({"src/parser.py": "pass"})

    with patch("httpx.Client") as mock_cls:
        mc = MagicMock()
        mc.__enter__ = MagicMock(return_value=mc)
        mc.__exit__ = MagicMock(return_value=False)
        mc.get = MagicMock(return_value=_mock_httpx_response(tarball))
        mock_cls.return_value = mc

        with patch("subprocess.run") as mock_run:
            _fetch_and_prepare_impl("tok", "owner", "repo", "abc123", [])

    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# _run_pytest_impl
# ---------------------------------------------------------------------------

def test_run_pytest_returns_test_list(tmp_path):
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([
        {"nodeid": "tests/test_parser.py::test_tok", "outcome": "passed"},
        {"nodeid": "tests/test_parser.py::test_bad", "outcome": "failed"},
    ]))
    proc = MagicMock(stdout="", stderr="", returncode=1)

    with patch("subprocess.run", return_value=proc):
        with patch("tempfile.mktemp", return_value=str(report_file)):
            result = _run_pytest_impl(tmp_path)

    assert len(result) == 2
    assert result[0]["outcome"] == "passed"


def test_run_pytest_returns_empty_on_missing_report(tmp_path):
    proc = MagicMock(stdout="crash", stderr="", returncode=2)

    with patch("subprocess.run", return_value=proc):
        with patch("tempfile.mktemp", return_value="/nonexistent/report.json"):
            result = _run_pytest_impl(tmp_path)

    assert result == []


def test_run_pytest_uses_test_ids_as_positional_args(tmp_path):
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([]))
    proc = MagicMock(stdout="", stderr="", returncode=0)

    with patch("subprocess.run", return_value=proc) as mock_run:
        with patch("tempfile.mktemp", return_value=str(report_file)):
            _run_pytest_impl(tmp_path, test_ids=["tests/test_foo.py::test_a"])

    cmd = mock_run.call_args[0][0]
    assert "tests/test_foo.py::test_a" in cmd
    # Should NOT include str(tmp_path) when test_ids are given
    assert str(tmp_path) not in cmd


# ---------------------------------------------------------------------------
# _discover_pr_fixed_tests_impl
# ---------------------------------------------------------------------------

def test_discover_returns_intersection():
    """Tests failing at base AND passing at head are returned."""
    base_tests = [
        {"nodeid": "tests/test_a.py::test_1", "outcome": "failed"},
        {"nodeid": "tests/test_a.py::test_2", "outcome": "passed"},
        {"nodeid": "tests/test_a.py::test_3", "outcome": "failed"},
    ]
    head_tests = [
        {"nodeid": "tests/test_a.py::test_1", "outcome": "passed"},  # fixed!
        {"nodeid": "tests/test_a.py::test_2", "outcome": "passed"},
        {"nodeid": "tests/test_a.py::test_3", "outcome": "failed"},  # still failing
    ]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_prep:
        mock_prep.return_value = Path("/fake/root")
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_pytest.side_effect = [base_tests, head_tests]
            result = _discover_pr_fixed_tests_impl(
                "tok", "owner", "repo", "base_sha", "head_sha", []
            )

    assert result == ["tests/test_a.py::test_1"]


def test_discover_excludes_always_failing():
    base_tests = [{"nodeid": "tests/test_a.py::test_always_fail", "outcome": "failed"}]
    head_tests = [{"nodeid": "tests/test_a.py::test_always_fail", "outcome": "failed"}]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_prep:
        mock_prep.return_value = Path("/fake/root")
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_pytest.side_effect = [base_tests, head_tests]
            result = _discover_pr_fixed_tests_impl(
                "tok", "owner", "repo", "base_sha", "head_sha", []
            )

    assert result == []


def test_discover_returns_sorted():
    base_tests = [
        {"nodeid": "tests/test_b.py::test_z", "outcome": "failed"},
        {"nodeid": "tests/test_a.py::test_a", "outcome": "failed"},
    ]
    head_tests = [
        {"nodeid": "tests/test_b.py::test_z", "outcome": "passed"},
        {"nodeid": "tests/test_a.py::test_a", "outcome": "passed"},
    ]

    with patch("integrations.github_runner._fetch_and_prepare_impl") as mock_prep:
        mock_prep.return_value = Path("/fake/root")
        with patch("integrations.github_runner._run_pytest_impl") as mock_pytest:
            mock_pytest.side_effect = [base_tests, head_tests]
            result = _discover_pr_fixed_tests_impl(
                "tok", "owner", "repo", "base_sha", "head_sha", []
            )

    assert result == sorted(result)


# ---------------------------------------------------------------------------
# _run_tests_impl — injection
# ---------------------------------------------------------------------------

ORIG_SOURCE = """\
def tokenize(s: str) -> list[str]:
    # buggy: uses split
    return s.split()

def helper():
    return 42
"""

CANDIDATE_GOOD = """\
def tokenize(s: str) -> list[str]:
    # fixed
    import re
    return re.findall(r'\\w+|[^\\w\\s]', s)
"""

CANDIDATE_NEW_FN = """\
def tokenize(s: str) -> list[str]:
    return s.split()

def new_helper():
    return 99
"""


def test_run_tests_impl_syntax_error():
    bad_code = "def foo(: pass"

    with patch("integrations.github_runner._fetch_and_prepare_impl"):
        result, stdout = _run_tests_impl(
            "tok", "owner", "repo", "base_sha",
            "src/parser.py", bad_code, [], [],
        )

    assert result[0]["name"] == "syntax_error"
    assert result[0]["passed"] is False


def test_run_tests_impl_replaces_function(tmp_path):
    repo_root = _prep_repo(tmp_path, ORIG_SOURCE)
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([
        {"nodeid": "tests/test_parser.py::test_tok", "outcome": "passed"},
    ]))
    proc = MagicMock(stdout="1 passed", stderr="", returncode=0)

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run", return_value=proc):
            with patch("tempfile.mktemp", return_value=str(report_file)):
                result, stdout = _run_tests_impl(
                    "tok", "owner", "repo", "base_sha",
                    "src/parser.py", CANDIDATE_GOOD, [], [],
                )

    modified = (repo_root / "src" / "parser.py").read_text()
    assert "# fixed" in modified
    assert "# buggy" not in modified
    assert "def helper" in modified  # unchanged function still present
    assert result[0]["passed"] is True


def test_run_tests_impl_appends_new_function(tmp_path):
    repo_root = _prep_repo(tmp_path, ORIG_SOURCE)
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([]))
    proc = MagicMock(stdout="", stderr="", returncode=0)

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run", return_value=proc):
            with patch("tempfile.mktemp", return_value=str(report_file)):
                _run_tests_impl(
                    "tok", "owner", "repo", "base_sha",
                    "src/parser.py", CANDIDATE_NEW_FN, [], [],
                )

    modified = (repo_root / "src" / "parser.py").read_text()
    assert "def new_helper" in modified


def test_run_tests_impl_passes_test_ids_to_pytest(tmp_path):
    repo_root = _prep_repo(tmp_path, ORIG_SOURCE)
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([]))
    proc = MagicMock(stdout="", stderr="", returncode=0)
    test_ids = ["tests/test_parser.py::test_tok"]

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run", return_value=proc) as mock_run:
            with patch("tempfile.mktemp", return_value=str(report_file)):
                _run_tests_impl(
                    "tok", "owner", "repo", "base_sha",
                    "src/parser.py", "def tokenize(s): return []", [], test_ids,
                )

    cmd = mock_run.call_args[0][0]
    assert "tests/test_parser.py::test_tok" in cmd


def test_run_tests_impl_empty_test_ids_uses_full_suite(tmp_path):
    repo_root = _prep_repo(tmp_path, ORIG_SOURCE)
    report_file = tmp_path / "report.json"
    report_file.write_text(_make_pytest_report([]))
    proc = MagicMock(stdout="", stderr="", returncode=0)

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run", return_value=proc) as mock_run:
            with patch("tempfile.mktemp", return_value=str(report_file)):
                _run_tests_impl(
                    "tok", "owner", "repo", "base_sha",
                    "src/parser.py", "def tokenize(s): return []", [], [],
                )

    cmd = mock_run.call_args[0][0]
    assert str(repo_root) in cmd


def test_run_tests_impl_malformed_report(tmp_path):
    repo_root = _prep_repo(tmp_path, ORIG_SOURCE)
    proc = MagicMock(stdout="crash output", stderr="", returncode=2)

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run", return_value=proc):
            with patch("tempfile.mktemp", return_value="/nonexistent/path.json"):
                result, stdout = _run_tests_impl(
                    "tok", "owner", "repo", "base_sha",
                    "src/parser.py", "def tokenize(s): return []", [], [],
                )

    assert result[0]["name"] == "pytest_parse_failed"
    assert result[0]["passed"] is False


def test_run_tests_impl_source_file_unparseable(tmp_path):
    """Original file with invalid Python → source_file_unparseable, no subprocess called."""
    repo_root = _prep_repo(tmp_path, "def foo(: broken syntax")

    with patch("integrations.github_runner._fetch_and_prepare_impl", return_value=repo_root):
        with patch("subprocess.run") as mock_run:
            result, stdout = _run_tests_impl(
                "tok", "owner", "repo", "base_sha",
                "src/parser.py", "def tokenize(s): return []", [], [],
            )

    assert result[0]["name"] == "source_file_unparseable"
    assert result[0]["passed"] is False
    assert stdout == ""
    mock_run.assert_not_called()
