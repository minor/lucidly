"""
Diagnostic script for troubleshooting discover_pr_fixed_tests.

Runs the discovery logic locally (no Modal) with verbose output at each step.

Usage:
    uv run python scripts/debug_discovery.py <github_token> <pr_url>

Example:
    uv run python scripts/debug_discovery.py ghp_xxx https://github.com/tigeyshark22/linear-github-test-fixture/pull/1
"""

import sys
import subprocess
import tempfile
from pathlib import Path

# Make sure we can import from the backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import tarfile as tarfile_mod

GITHUB_API_BASE = "https://api.github.com"


def fetch_pr_info(token: str, owner: str, repo: str, pr_number: int) -> dict:
    with httpx.Client() as client:
        resp = client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()


def fetch_pr_files(token: str, owner: str, repo: str, pr_number: int) -> list[dict]:
    with httpx.Client() as client:
        resp = client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()


def fetch_and_prepare(token: str, owner: str, repo: str, sha: str, label: str) -> Path:
    print(f"\n--- Fetching repo at {label} SHA {sha[:8]} ---")
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/tarball/{sha}"
    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()

    extract_dir = Path(tempfile.mkdtemp())
    tarball_path = extract_dir / "repo.tar.gz"
    tarball_path.write_bytes(resp.content)
    print(f"  Downloaded {len(resp.content) // 1024}KB to {extract_dir}")

    with tarfile_mod.open(tarball_path) as tf:
        tf.extractall(extract_dir)

    subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
    print(f"  Top-level dirs after extract: {[d.name for d in subdirs]}")
    repo_root = subdirs[0]

    print(f"  Repo root: {repo_root}")
    print(f"  Files in root: {[f.name for f in repo_root.iterdir()]}")

    req_txt = repo_root / "requirements.txt"
    if req_txt.exists():
        print(f"  Installing requirements.txt...")
        result = subprocess.run(
            ["pip", "install", "-r", str(req_txt), "-q"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  WARNING: pip install failed:\n{result.stderr}")
    else:
        print(f"  No requirements.txt found")

    return repo_root


def run_pytest_verbose(repo_root: Path, label: str) -> list[dict]:
    import json
    print(f"\n--- Running pytest at {label} ---")
    report_path = tempfile.mktemp(suffix="_pytest_report.json")
    result = subprocess.run(
        ["pytest", str(repo_root), "--tb=short", "-v",
         "--json-report", f"--json-report-file={report_path}"],
        capture_output=True, text=True,
    )
    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        print(f"  STDOUT:\n{result.stdout[:3000]}")
    if result.stderr:
        print(f"  STDERR:\n{result.stderr[:1000]}")

    try:
        with open(report_path) as f:
            report = json.load(f)
        tests = report.get("tests", [])
        print(f"  Tests found: {len(tests)}")
        for t in tests:
            print(f"    [{t.get('outcome', '?').upper():7}] {t['nodeid']}")
        return tests
    except Exception as e:
        print(f"  Failed to parse pytest JSON report: {e}")
        return []


def parse_pr_url(pr_url: str):
    import re
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"Not a valid PR URL: {pr_url}")
    return m.group(1), m.group(2), int(m.group(3))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    token = sys.argv[1]
    pr_url = sys.argv[2]

    owner, repo, pr_number = parse_pr_url(pr_url)
    print(f"Repo: {owner}/{repo}  PR: #{pr_number}")

    # 1. Fetch PR metadata
    pr_data = fetch_pr_info(token, owner, repo, pr_number)
    base_sha = pr_data["base"]["sha"]
    head_sha = pr_data["head"]["sha"]
    is_merged = bool(pr_data.get("merged_at"))
    print(f"base_sha: {base_sha[:8]}  head_sha: {head_sha[:8]}  is_merged: {is_merged}")

    if not is_merged:
        print("\nWARNING: PR is not merged. The enriched starter-code path requires is_merged=True.")

    # 2. Show changed files
    files = fetch_pr_files(token, owner, repo, pr_number)
    print(f"\nChanged files ({len(files)}):")
    for f in files:
        print(f"  {f['filename']}")

    # 3. Run at base SHA
    base_root = fetch_and_prepare(token, owner, repo, base_sha, "base")
    base_tests = run_pytest_verbose(base_root, "base")
    failing_at_base = {t["nodeid"] for t in base_tests if t.get("outcome") != "passed"}
    print(f"\nFailing at base: {sorted(failing_at_base) or '(none)'}")

    # 4. Run at head SHA
    head_root = fetch_and_prepare(token, owner, repo, head_sha, "head")
    head_tests = run_pytest_verbose(head_root, "head")
    passing_at_head = {t["nodeid"] for t in head_tests if t.get("outcome") == "passed"}
    print(f"\nPassing at head: {sorted(passing_at_head) or '(none)'}")

    # 5. Intersection = PR-fixed tests
    fixed = sorted(failing_at_base & passing_at_head)
    print(f"\n=== PR-fixed test IDs ({len(fixed)}) ===")
    for t in fixed:
        print(f"  {t}")
    if not fixed:
        print("  (none — discovery will fall back to diff/test-case name extraction)")


if __name__ == "__main__":
    main()
