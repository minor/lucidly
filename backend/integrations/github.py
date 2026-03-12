"""GitHub OAuth client and REST API helpers."""

import re
import urllib.parse
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
        return resp.json()["access_token"]


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


def _candidate_test_paths(changed_files: list[dict]) -> list[str]:
    """Generate candidate test file paths for a list of changed source files."""
    candidates = []
    for f in changed_files:
        name = f["filename"]
        basename = name.split("/")[-1]
        stem = basename.replace(".py", "").replace(".ts", "").replace(".js", "")
        candidates.append(f"tests/test_{stem}.py")
        candidates.append(f"tests/{stem}_test.py")
        candidates.append(f"__tests__/{stem}.test.ts")
        dir_part = "/".join(name.split("/")[:-1])
        if dir_part:
            candidates.append(f"{dir_part}/tests/test_{stem}.py")
    return list(dict.fromkeys(candidates))  # deduplicate, preserve order


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


async def find_test_file_content(
    token: str, owner: str, repo: str, changed_files: list[dict], ref: str = "HEAD"
) -> list[str]:
    """Return content of any test files found for the changed source files."""
    candidates = _candidate_test_paths(changed_files)
    found = []
    for path in candidates:
        content = await get_file_content(token, owner, repo, path, ref)
        if content:
            found.append(content)
    return found


async def get_pr_info(token: str, pr_url: str) -> tuple[list[dict], list[str], str] | None:
    """
    Given a GitHub PR URL, return (changed_files, test_file_contents, head_sha).
    Returns None if the URL can't be parsed.
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
        head_sha = pr_resp.json()["head"]["sha"]

    changed_files = await get_pr_changed_files(token, owner, repo, pr_number)
    test_contents = await find_test_file_content(token, owner, repo, changed_files, ref=head_sha)
    return changed_files, test_contents, head_sha
