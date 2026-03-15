"""
Modal-based GitHub repo execution for PR-fixed test discovery and evaluation.

Public API:
  discover_pr_fixed_tests(token, owner, repo, base_sha, head_sha, test_files) -> list[str]
  run_in_repo_context(token, owner, repo, base_sha, test_files, file_path, solution, test_ids) -> list[dict]

The _impl functions contain the core logic and are unit-testable without Modal.
Modal-decorated wrappers call the _impl functions.
"""
import ast
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

import httpx

GITHUB_API_BASE = "https://api.github.com"
TARBALL_URL = "https://api.github.com/repos/{owner}/{repo}/tarball/{sha}"


# ---------------------------------------------------------------------------
# Core implementation functions (no Modal, unit-testable)
# ---------------------------------------------------------------------------

def _fetch_and_prepare_impl(
    token: str,
    owner: str,
    repo: str,
    sha: str,
    test_files: list[dict],
) -> Path:
    """
    Download repo tarball at `sha`, extract to a temp dir, write test files,
    install requirements if present. Returns the repo root Path.
    """
    url = TARBALL_URL.format(owner=owner, repo=repo, sha=sha)
    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        tarball_bytes = resp.content

    tmp_dir = Path(tempfile.mkdtemp())
    buf = io.BytesIO(tarball_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        tf.extractall(tmp_dir)

    # GitHub tarballs extract to a single top-level directory like "owner-repo-sha/"
    subdirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
    repo_root = subdirs[0] if subdirs else tmp_dir

    # Write test files (override whatever was in the tarball)
    for tf_entry in test_files:
        dest = repo_root / tf_entry["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tf_entry["content"])

    # Install dependencies if requirements.txt exists
    req_file = repo_root / "requirements.txt"
    if req_file.exists():
        subprocess.run(
            ["pip", "install", "-r", str(req_file)],
            cwd=str(repo_root),
            check=True,
        )

    return repo_root


def _run_pytest_impl(repo_root: Path, test_ids: list[str] | None = None) -> list[dict]:
    """
    Run pytest in `repo_root`, optionally scoped to `test_ids`.
    Returns the list of test result dicts from the JSON report.
    """
    report_path = tempfile.mktemp(suffix=".json")
    cmd = [
        "python", "-m", "pytest",
        "--json-report",
        f"--json-report-file={report_path}",
        "-q",
    ]
    if test_ids:
        cmd.extend(test_ids)

    subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

    try:
        report = json.loads(Path(report_path).read_text())
        return report.get("tests", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _discover_pr_fixed_tests_impl(
    token: str,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    test_files: list[dict],
) -> list[str]:
    """
    Discover tests that fail at base_sha but pass at head_sha (PR-fixed tests).
    Returns list of pytest node IDs.
    """
    base_root = _fetch_and_prepare_impl(token, owner, repo, base_sha, test_files)
    base_results = _run_pytest_impl(base_root)
    failing_at_base = {r["nodeid"] for r in base_results if r.get("outcome") == "failed"}

    head_root = _fetch_and_prepare_impl(token, owner, repo, head_sha, test_files)
    head_results = _run_pytest_impl(head_root)
    passing_at_head = {r["nodeid"] for r in head_results if r.get("outcome") == "passed"}

    return sorted(failing_at_base & passing_at_head)


def _run_tests_impl(
    token: str,
    owner: str,
    repo: str,
    base_sha: str,
    test_files: list[dict],
    file_path: str,
    solution: str,
    test_ids: list[str],
) -> list[dict]:
    """
    Inject `solution` into `file_path` in the repo at `base_sha`, then run `test_ids`.
    Raises SyntaxError if solution is not valid Python.
    Returns list of test result dicts.
    """
    ast.parse(solution)  # raises SyntaxError if invalid

    repo_root = _fetch_and_prepare_impl(token, owner, repo, base_sha, test_files)
    target = repo_root / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(solution)

    return _run_pytest_impl(repo_root, test_ids=test_ids)


# ---------------------------------------------------------------------------
# Modal app (wraps _impl functions for sandboxed execution)
# ---------------------------------------------------------------------------

try:
    import modal

    app = modal.App("lucidly-github-runner")
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install("httpx", "pytest", "pytest-json-report")
    )

    @app.function(image=image, timeout=300)
    def _discover_pr_fixed_tests(
        token: str,
        owner: str,
        repo: str,
        base_sha: str,
        head_sha: str,
        test_files: list[dict],
    ) -> list[str]:
        return _discover_pr_fixed_tests_impl(token, owner, repo, base_sha, head_sha, test_files)

    @app.function(image=image, timeout=300)
    def _run_tests(
        token: str,
        owner: str,
        repo: str,
        base_sha: str,
        test_files: list[dict],
        file_path: str,
        solution: str,
        test_ids: list[str],
    ) -> list[dict]:
        return _run_tests_impl(token, owner, repo, base_sha, test_files, file_path, solution, test_ids)

except ImportError:
    # Modal not installed (e.g., in test environments) — _impl functions still available
    _discover_pr_fixed_tests = None
    _run_tests = None


# ---------------------------------------------------------------------------
# Async public API (called from FastAPI handlers)
# ---------------------------------------------------------------------------

async def discover_pr_fixed_tests(
    token: str,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    test_files: list[dict],
) -> list[str]:
    """Discover PR-fixed test IDs via Modal sandbox."""
    if _discover_pr_fixed_tests is None:
        return _discover_pr_fixed_tests_impl(token, owner, repo, base_sha, head_sha, test_files)
    return await _discover_pr_fixed_tests.remote.aio(token, owner, repo, base_sha, head_sha, test_files)


async def run_in_repo_context(
    token: str,
    owner: str,
    repo: str,
    base_sha: str,
    test_files: list[dict],
    file_path: str,
    solution: str,
    test_ids: list[str],
) -> list[dict]:
    """Inject solution and run scoped tests via Modal sandbox."""
    if _run_tests is None:
        return _run_tests_impl(token, owner, repo, base_sha, test_files, file_path, solution, test_ids)
    return await _run_tests.remote.aio(token, owner, repo, base_sha, test_files, file_path, solution, test_ids)
