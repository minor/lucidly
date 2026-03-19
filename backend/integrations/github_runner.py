"""Modal-based GitHub repo execution for challenge creation and evaluation."""
import ast
import json
import os
import subprocess
import tarfile
import tempfile
import logging
from pathlib import Path

import httpx
import modal
from pydantic import BaseModel


class RepoContext(BaseModel):
    owner: str
    repo: str
    base_sha: str
    file_paths: list[str]
    challenge_test_ids: list[str]
    github_token: str | None = None
    file_path: str | None = None  # legacy

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx", "pytest", "pytest-json-report")
)
app = modal.App("lucidly-github-runner")


# ---------------------------------------------------------------------------
# Shared helpers (module-level, callable in tests without Modal)
# ---------------------------------------------------------------------------

def _fetch_and_prepare_impl(
    github_token: str,
    owner: str,
    repo: str,
    sha: str,
    test_files: list[dict],
) -> Path:
    """Fetch repo tarball at sha, extract, write test files, install deps. Returns repo root."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/tarball/{sha}"
    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        tarball_bytes = resp.content

    extract_dir = Path(tempfile.mkdtemp())
    tarball_path = extract_dir / "repo.tar.gz"
    tarball_path.write_bytes(tarball_bytes)

    with tarfile.open(tarball_path) as tf:
        tf.extractall(extract_dir)

    subdirs = [d for d in extract_dir.iterdir() if d.is_dir() and d.name != "repo.tar.gz"]
    if len(subdirs) != 1:
        raise RuntimeError(f"unexpected tarball structure: {len(subdirs)} top-level dirs")
    repo_root = subdirs[0]

    for tf_entry in test_files:
        dest = repo_root / tf_entry["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tf_entry["content"])

    req_txt = repo_root / "requirements.txt"
    if req_txt.exists():
        subprocess.run(["pip", "install", "-r", str(req_txt), "-q"], check=False)

    return repo_root


def _run_pytest_impl(repo_root: Path, test_ids: list[str] | None = None) -> list[dict]:
    """Run pytest, return list of test dicts from JSON report. Returns [] on parse failure."""
    report_path = tempfile.mktemp(suffix="_pytest_report.json")
    args = test_ids if test_ids else [str(repo_root)]
    subprocess.run(
        ["pytest", *args, "--tb=no", "-q", "--json-report", f"--json-report-file={report_path}"],
        capture_output=True, text=True,
        cwd=str(repo_root),
    )
    try:
        with open(report_path) as f:
            report = json.load(f)
        return report.get("tests", [])
    except Exception:
        return []


def _discover_pr_fixed_tests_impl(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    test_files: list[dict],
) -> list[str]:
    """Return test node IDs that fail at base_sha but pass at head_sha."""
    base_root = _fetch_and_prepare_impl(github_token, owner, repo, base_sha, test_files)
    base_results = _run_pytest_impl(base_root)
    failing_at_base = {t["nodeid"] for t in base_results if t.get("outcome") != "passed"}

    head_root = _fetch_and_prepare_impl(github_token, owner, repo, head_sha, test_files)
    head_results = _run_pytest_impl(head_root)
    passing_at_head = {t["nodeid"] for t in head_results if t.get("outcome") == "passed"}

    return sorted(failing_at_base & passing_at_head)


FILE_SEPARATOR_PREFIX = "# === FILE: "
FILE_SEPARATOR_SUFFIX = " ==="


def _write_candidate_files(repo_root: Path, file_paths: list[str], candidate_code: str) -> str | None:
    """
    Write candidate_code into the repo. Supports two formats:
      - Multi-file: sections delimited by '# === FILE: path/to/file.py ==='
      - Single-file: candidate_code written directly to file_paths[0]
    Returns a syntax error message if any section fails to parse, else None.
    """
    import re
    separator_re = re.compile(r"^# === FILE: (.+?) ===$", re.MULTILINE)
    parts = separator_re.split(candidate_code.strip())

    if len(parts) > 1:
        # Multi-file format: ['', 'path1', 'content1', 'path2', 'content2', ...]
        it = iter(parts[1:])
        for fname, content in zip(it, it):
            fname = fname.strip()
            content = content.strip()
            try:
                ast.parse(content)
            except SyntaxError as e:
                return f"SyntaxError in {fname}: {e}"
            dest = repo_root / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content + "\n")
    else:
        # Single-file: write to the first (and presumably only) file path
        try:
            ast.parse(candidate_code)
        except SyntaxError as e:
            return str(e)
        dest = repo_root / file_paths[0]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(candidate_code)
    return None


def _run_tests_impl(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    file_paths: list[str],
    candidate_code: str,
    test_files: list[dict],
    challenge_test_ids: list[str],
) -> tuple[list[dict], str]:
    """Write candidate_code into repo at base_sha, run PR-fixed tests. Returns (results, stdout)."""
    # 1. Fetch and prepare
    repo_root = _fetch_and_prepare_impl(github_token, owner, repo, base_sha, test_files)

    # 2. Write candidate code (single or multi-file)
    err = _write_candidate_files(repo_root, file_paths, candidate_code)
    if err:
        return [{"name": "syntax_error", "passed": False, "message": err}], ""

    # 7. Run pytest
    report_path = tempfile.mktemp(suffix="_pytest_report.json")
    if challenge_test_ids:
        pytest_args = challenge_test_ids  # relative node IDs — needs cwd=repo_root
        print(f"[_run_tests_impl] running {len(pytest_args)} specific test(s): {pytest_args}", flush=True)
    else:
        pytest_args = [str(repo_root)]
        print(f"[_run_tests_impl] no specific tests — running full suite at {repo_root}", flush=True)
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    result = subprocess.run(
        ["pytest", *pytest_args, "--tb=short", "-q", "--json-report", f"--json-report-file={report_path}"],
        capture_output=True, text=True,
        cwd=str(repo_root),
        env=env,
    )
    pytest_stdout = result.stdout + result.stderr

    # 8. Parse report
    try:
        with open(report_path) as f:
            report = json.load(f)
        tests = report.get("tests", [])
        results = [
            {
                "name": t["nodeid"],
                "passed": t["outcome"] == "passed",
                "message": (
                    t.get("call", {}).get("longrepr", "")
                    if t["outcome"] != "passed"
                    else ""
                ),
            }
            for t in tests
        ]
        if not results:
            # No tests collected — likely a syntax/import error in the submitted file
            return [{"name": "collection_error", "passed": False, "message": pytest_stdout[:2000]}], pytest_stdout
        return results, pytest_stdout
    except Exception:
        return [{"name": "pytest_parse_failed", "passed": False, "message": pytest_stdout[:2000]}], pytest_stdout


# ---------------------------------------------------------------------------
# Modal functions (call _impl functions)
# ---------------------------------------------------------------------------

@app.function(image=image, timeout=180)
def _discover_pr_fixed_tests(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    test_files: list[dict],
) -> list[str]:
    return _discover_pr_fixed_tests_impl(
        github_token, owner, repo, base_sha, head_sha, test_files
    )


@app.function(image=image, timeout=120)
def _run_tests(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    file_paths: list[str],
    candidate_code: str,
    test_files: list[dict],
    challenge_test_ids: list[str],
) -> tuple[list[dict], str]:
    return _run_tests_impl(
        github_token, owner, repo, base_sha, file_paths,
        candidate_code, test_files, challenge_test_ids,
    )


# ---------------------------------------------------------------------------
# Async wrappers for FastAPI / evaluator
# ---------------------------------------------------------------------------

async def discover_pr_fixed_tests(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    test_files: list[dict],
) -> list[str]:
    logger.info(
        "[github_runner] calling discover_pr_fixed_tests via Modal: %s/%s base=%s head=%s",
        owner, repo, base_sha[:8], head_sha[:8],
    )
    try:
        fn = modal.Function.from_name("lucidly-github-runner", "_discover_pr_fixed_tests")
        result = await fn.remote.aio(
            github_token, owner, repo, base_sha, head_sha, test_files
        )
        logger.info("[github_runner] Modal returned %d test ID(s): %s", len(result), result)
        return result
    except Exception as e:
        logger.warning("[github_runner] discover_pr_fixed_tests failed: %s", e)
        return []


async def run_in_repo_context(
    github_token: str,
    repo_context: RepoContext,
    candidate_code: str,
    test_files: list[dict],
) -> tuple[list[dict], str]:
    try:
        # Support legacy single-file repo_context rows
        file_paths = repo_context.file_paths or ([repo_context.file_path] if repo_context.file_path else [])
        fn = modal.Function.from_name("lucidly-github-runner", "_run_tests")
        return await fn.remote.aio(
            github_token,
            repo_context.owner,
            repo_context.repo,
            repo_context.base_sha,
            file_paths,
            candidate_code,
            test_files,
            repo_context.challenge_test_ids,
        )
    except Exception as e:
        return ([{"name": "execution_failed", "passed": False, "message": str(e)}], "")
