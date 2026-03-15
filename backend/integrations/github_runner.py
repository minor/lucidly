"""Modal-based GitHub repo execution for challenge creation and evaluation."""
import ast
import json
import subprocess
import tarfile
import tempfile
import logging
from pathlib import Path

import httpx
import modal

from challenges import RepoContext

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


def _run_tests_impl(
    github_token: str,
    owner: str,
    repo: str,
    base_sha: str,
    file_path: str,
    candidate_code: str,
    test_files: list[dict],
    challenge_test_ids: list[str],
) -> tuple[list[dict], str]:
    """Inject candidate_code into repo at base_sha, run PR-fixed tests. Returns (results, stdout)."""
    # 1. Syntax check candidate
    try:
        candidate_tree = ast.parse(candidate_code)
    except SyntaxError as e:
        return [{"name": "syntax_error", "passed": False, "message": str(e)}], ""

    # 2. Fetch and prepare
    repo_root = _fetch_and_prepare_impl(github_token, owner, repo, base_sha, test_files)

    # 3. Parse original file
    orig_path = repo_root / file_path
    try:
        orig_src = orig_path.read_text()
        orig_tree = ast.parse(orig_src)
    except Exception as e:
        return [{"name": "source_file_unparseable", "passed": False, "message": str(e)}], ""

    orig_lines = orig_src.splitlines(True)

    # 4. Build map of original top-level functions (last occurrence wins)
    orig_funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    orig_import_strs: set[str] = set()
    for node in orig_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            orig_funcs[node.name] = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(orig_src, node)
            if seg:
                orig_import_strs.add(seg)

    # 5. Collect candidate functions and new imports
    new_import_lines: list[str] = []
    replacements: dict[int, tuple[int, str]] = {}  # start_line -> (end_line, new_code)
    append_funcs: list[str] = []

    for node in candidate_tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(candidate_code, node)
            if seg and seg not in orig_import_strs:
                new_import_lines.append(seg + "\n")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = ast.get_source_segment(candidate_code, node)
            if seg:
                if node.name in orig_funcs:
                    orig_node = orig_funcs[node.name]
                    start = (
                        orig_node.decorator_list[0].lineno
                        if orig_node.decorator_list
                        else orig_node.lineno
                    )
                    end = orig_node.end_lineno
                    replacements[start] = (end, seg)
                else:
                    append_funcs.append(seg)

    # 6. Rebuild file
    new_parts: list[str] = []
    if new_import_lines:
        new_parts.extend(new_import_lines)

    i = 1  # 1-indexed
    while i <= len(orig_lines):
        if i in replacements:
            end, new_code = replacements[i]
            new_parts.append(new_code + "\n")
            i = end + 1
        else:
            new_parts.append(orig_lines[i - 1])
            i += 1

    for fn_code in append_funcs:
        new_parts.append("\n\n" + fn_code + "\n")

    orig_path.write_text("".join(new_parts))

    # 7. Run pytest
    report_path = tempfile.mktemp(suffix="_pytest_report.json")
    pytest_args = challenge_test_ids if challenge_test_ids else [str(repo_root)]
    result = subprocess.run(
        ["pytest", *pytest_args, "--tb=short", "-q", "--json-report", f"--json-report-file={report_path}"],
        capture_output=True, text=True,
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
    file_path: str,
    candidate_code: str,
    test_files: list[dict],
    challenge_test_ids: list[str],
) -> tuple[list[dict], str]:
    return _run_tests_impl(
        github_token, owner, repo, base_sha, file_path,
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
    try:
        return await _discover_pr_fixed_tests.remote.aio(
            github_token, owner, repo, base_sha, head_sha, test_files
        )
    except Exception as e:
        logger.warning("discover_pr_fixed_tests failed: %s", e)
        return []


async def run_in_repo_context(
    github_token: str,
    repo_context: RepoContext,
    candidate_code: str,
    test_files: list[dict],
) -> tuple[list[dict], str]:
    try:
        return await _run_tests.remote.aio(
            github_token,
            repo_context.owner,
            repo_context.repo,
            repo_context.base_sha,
            repo_context.file_path,
            candidate_code,
            test_files,
            repo_context.challenge_test_ids,
        )
    except Exception as e:
        return ([{"name": "execution_failed", "passed": False, "message": str(e)}], "")
