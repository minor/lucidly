"""GitHub OAuth client and REST API helpers."""

import asyncio
import re
import urllib.parse
from typing import TypedDict
import httpx
from config import settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"


def get_github_oauth_url(state: str) -> str:
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/github/callback"
    params = urllib.parse.urlencode({
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo",
        "state": state,
    })
    return f"{GITHUB_AUTHORIZE_URL}?{params}"


async def exchange_github_code(code: str) -> str:
    """Exchange authorization code for access token. Returns the access token."""
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/github/callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise ValueError(f"GitHub OAuth error: {data.get('error_description', data['error'])}")
        return data["access_token"]


def _parse_pr_url(pr_url: str) -> tuple[str, str, int] | None:
    """Parse 'https://github.com/owner/repo/pull/123' -> (owner, repo, 123)."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


async def get_pr_changed_files(token: str, owner: str, repo: str, pr_number: int) -> list[dict]:
    """Return list of {filename, patch} for a PR."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()



async def get_file_content(token: str, owner: str, repo: str, path: str, ref: str = "HEAD") -> str | None:
    """Fetch raw file content from GitHub. Returns None if not found."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.raw+json"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text


async def get_all_test_files(token: str, owner: str, repo: str, ref: str = "HEAD") -> list[str]:
    """Fetch all test files from common test directories in the repo."""
    test_dirs = ["tests", "__tests__", "test"]
    all_contents: list[str] = []

    async with httpx.AsyncClient() as client:
        for test_dir in test_dirs:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{test_dir}",
                params={"ref": ref},
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            entries = resp.json()
            if not isinstance(entries, list):
                continue
            test_files = [
                e["path"] for e in entries
                if e["type"] == "file" and _is_test_file(e["path"])
            ]
            results = await asyncio.gather(
                *[get_file_content(token, owner, repo, path, ref=ref) for path in test_files]
            )
            all_contents.extend(c for c in results if c)

    return all_contents


async def _get_check_run_annotations(token: str, owner: str, repo: str, check_run_id: int) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations",
            params={"per_page": 100},
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_ci_test_annotations(token: str, owner: str, repo: str, sha: str) -> list[dict]:
    """
    Return failure annotations from CI check runs for a commit.
    Annotations include test file paths and failure messages from pytest/jest/etc.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}/check-runs",
            params={"per_page": 100},
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        check_runs = resp.json().get("check_runs", [])

    all_annotations: list[dict] = []
    for run in check_runs:
        annotations = await _get_check_run_annotations(token, owner, repo, run["id"])
        failures = [a for a in annotations if a.get("annotation_level") in ("failure", "warning")]
        all_annotations.extend(failures)
    return all_annotations


class PRInfo(TypedDict):
    changed_files: list[dict]
    test_file_contents: list[str]
    ci_annotations: list[dict]
    base_source_files: list[dict]  # [{filename, content}] at base SHA — merged PRs only
    head_sha: str
    is_merged: bool


def _is_test_file(filename: str) -> bool:
    basename = filename.split("/")[-1]
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or basename.endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js"))
        or "/tests/" in filename
        or "/__tests__/" in filename
    )


async def get_pr_info(token: str, pr_url: str) -> PRInfo | None:
    """
    Given a GitHub PR URL, return a PRInfo dict.

    Merged PRs: test files are taken directly from files changed in the PR;
    source files at base SHA are returned as starter code (the buggy version).

    Open PRs: test files come from CI failure annotations, falling back to
    path guessing; no base source files.
    """
    parsed = _parse_pr_url(pr_url)
    if not parsed:
        return None
    owner, repo, pr_number = parsed

    async with httpx.AsyncClient() as client:
        pr_resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        )
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

    head_sha = pr_data["head"]["sha"]
    base_sha = pr_data["base"]["sha"]
    is_merged = bool(pr_data.get("merged_at"))

    changed_files = await get_pr_changed_files(token, owner, repo, pr_number)

    if is_merged:
        # Test files changed in the PR are the ground truth for the challenge
        test_filenames = [f["filename"] for f in changed_files if _is_test_file(f["filename"])]
        source_filenames = [f["filename"] for f in changed_files if not _is_test_file(f["filename"])]

        # Fetch all files in parallel: test files at head, source files at base (buggy version)
        n_tests = len(test_filenames)
        all_results = await asyncio.gather(
            *[get_file_content(token, owner, repo, p, ref=head_sha) for p in test_filenames],
            *[get_file_content(token, owner, repo, p, ref=base_sha) for p in source_filenames],
        )
        test_contents = await get_all_test_files(token, owner, repo, ref=head_sha)
        base_source_files = [
            {"filename": name, "content": content}
            for name, content in zip(source_filenames, all_results[n_tests:])
            if content
        ]
        return PRInfo(
            changed_files=changed_files,
            test_file_contents=test_contents,
            ci_annotations=[],
            base_source_files=base_source_files,
            head_sha=head_sha,
            is_merged=True,
        )
    else:
        ci_annotations = await get_ci_test_annotations(token, owner, repo, head_sha)
        test_contents = await get_all_test_files(token, owner, repo, ref=head_sha)
        return PRInfo(
            changed_files=changed_files,
            test_file_contents=test_contents,
            ci_annotations=ci_annotations,
            base_source_files=[],
            head_sha=head_sha,
            is_merged=False,
        )
