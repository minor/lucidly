# Linear + GitHub Integration for Interview Mode — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Import from Linear" button to interview challenge creation that auto-populates title, description, and test cases from a Linear issue + linked GitHub PR.

**Architecture:** Backend OAuth callbacks for Linear and GitHub store tokens per-user in Supabase. A `/api/integrations/generate-challenge` endpoint fetches the issue, finds linked PR diffs + test files, and uses an LLM to return structured challenge fields. Frontend shows inline OAuth popups on first use, then a searchable Linear issue picker modal.

**Tech Stack:** FastAPI (backend), Next.js 14 App Router (frontend), Supabase (token storage), Linear API v2, GitHub REST API, existing `LLM` class for generation.

---

## Parallelization Map

These task groups can be dispatched in parallel:

- **Round 1 (all independent):** Task 1, Task 2, Task 3, Task 7
- **Round 2 (after Round 1):** Task 4, Task 8
- **Round 3 (after Round 2):** Task 5, Task 9
- **Round 4 (after Round 3):** Task 6, Task 10

---

## Task 1: DB Migration + Config

**Files:**
- Create: `backend/migrations/add_user_integrations.sql`
- Modify: `backend/config.py`

**Step 1: Create the migration SQL**

```sql
-- backend/migrations/add_user_integrations.sql
CREATE TABLE IF NOT EXISTS user_integrations (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       TEXT        NOT NULL,
  provider      TEXT        NOT NULL CHECK (provider IN ('linear', 'github')),
  access_token  TEXT        NOT NULL,
  refresh_token TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, provider)
);
```

Run this manually in Supabase SQL editor or via migration tool.

**Step 2: Add config keys to `backend/config.py`**

Add to the `Settings` class (after the `supabase_service_key` field):

```python
# Linear OAuth
linear_client_id: str = ""
linear_client_secret: str = ""

# GitHub OAuth
github_oauth_client_id: str = ""
github_oauth_client_secret: str = ""

# Base URL for OAuth redirect URIs (e.g. https://app.lucidly.com or http://localhost:8000)
integration_redirect_base_url: str = "http://localhost:8000"
```

**Step 3: Verify settings load**

```bash
cd backend && python -c "from config import settings; print(settings.linear_client_id)"
```
Expected: empty string (no error)

**Step 4: Commit**

```bash
git add backend/migrations/add_user_integrations.sql backend/config.py
git commit -m "feat: add user_integrations table migration and OAuth config keys"
```

---

## Task 2: Linear API Client

**Files:**
- Create: `backend/integrations/__init__.py`
- Create: `backend/integrations/linear.py`

**Step 1: Write the failing test**

Create `backend/tests/test_linear_client.py`:

```python
"""Unit tests for Linear API client (all HTTP calls mocked)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.linear import (
    get_linear_oauth_url,
    exchange_linear_code,
    get_linear_issues,
    get_linear_issue,
)


def test_oauth_url_contains_client_id():
    url = get_linear_oauth_url(state="abc123")
    assert "linear.app/oauth/authorize" in url
    assert "abc123" in url


@pytest.mark.asyncio
async def test_exchange_code_returns_token():
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok_test", "token_type": "Bearer"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = await exchange_linear_code("code123")
        assert token == "tok_test"


@pytest.mark.asyncio
async def test_get_linear_issues_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "issues": {
                "nodes": [
                    {"id": "abc", "identifier": "ENG-1", "title": "Fix bug", "description": "desc", "branchName": "eng-1-fix-bug"}
                ]
            }
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        issues = await get_linear_issues("tok_test", query="Fix")
        assert len(issues) == 1
        assert issues[0]["identifier"] == "ENG-1"
```

**Step 2: Run to verify failure**

```bash
cd backend && python -m pytest tests/test_linear_client.py -v
```
Expected: `ImportError: cannot import name 'get_linear_oauth_url' from 'integrations.linear'`

**Step 3: Create `backend/integrations/__init__.py`**

```python
```
(empty file)

**Step 4: Implement `backend/integrations/linear.py`**

```python
"""Linear OAuth client and API helpers."""

import hashlib
import hmac
import secrets
import httpx
from config import settings

LINEAR_AUTHORIZE_URL = "https://linear.app/oauth/authorize"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_API_URL = "https://api.linear.app/graphql"


def get_linear_oauth_url(state: str) -> str:
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/linear/callback"
    params = (
        f"client_id={settings.linear_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read"
        f"&state={state}"
    )
    return f"{LINEAR_AUTHORIZE_URL}?{params}"


async def exchange_linear_code(code: str) -> str:
    """Exchange authorization code for access token. Returns the access token."""
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/linear/callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LINEAR_TOKEN_URL,
            data={
                "client_id": settings.linear_client_id,
                "client_secret": settings.linear_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def get_linear_issues(token: str, query: str = "") -> list[dict]:
    """Search or list issues from the user's Linear workspace."""
    gql = """
    query Issues($filter: IssueFilter) {
      issues(filter: $filter, first: 25, orderBy: updatedAt) {
        nodes {
          id
          identifier
          title
          description
          branchName
          url
          attachments { nodes { url sourceType } }
        }
      }
    }
    """
    variables: dict = {}
    if query:
        variables["filter"] = {"title": {"containsIgnoreCase": query}}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LINEAR_API_URL,
            json={"query": gql, "variables": variables},
            headers={"Authorization": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["issues"]["nodes"]


async def get_linear_issue(token: str, issue_id: str) -> dict:
    """Fetch a single Linear issue by ID."""
    gql = """
    query Issue($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        description
        branchName
        url
        attachments { nodes { url sourceType } }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LINEAR_API_URL,
            json={"query": gql, "variables": {"id": issue_id}},
            headers={"Authorization": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()["data"]["issue"]


def get_github_pr_numbers_from_issue(issue: dict) -> list[str]:
    """Extract GitHub PR URLs from Linear issue attachments."""
    pr_urls = []
    attachments = issue.get("attachments", {}).get("nodes", [])
    for att in attachments:
        if att.get("sourceType") == "github_pull_request" or "github.com" in att.get("url", ""):
            if "/pull/" in att.get("url", ""):
                pr_urls.append(att["url"])
    return pr_urls
```

**Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_linear_client.py -v
```
Expected: all 3 tests PASS

**Step 6: Commit**

```bash
git add backend/integrations/__init__.py backend/integrations/linear.py backend/tests/test_linear_client.py
git commit -m "feat: add Linear OAuth client and GraphQL API helpers"
```

---

## Task 3: GitHub API Client

**Files:**
- Create: `backend/integrations/github.py`

**Step 1: Write the failing test**

Create `backend/tests/test_github_client.py`:

```python
"""Unit tests for GitHub API client (all HTTP calls mocked)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.github import (
    get_github_oauth_url,
    exchange_github_code,
    get_pr_changed_files,
    find_test_file_content,
    get_file_content,
)


def test_oauth_url_contains_client_id():
    url = get_github_oauth_url(state="xyz")
    assert "github.com/login/oauth/authorize" in url
    assert "xyz" in url
    assert "repo" in url  # must request repo scope


@pytest.mark.asyncio
async def test_exchange_code_returns_token():
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "ghp_test"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mc

        token = await exchange_github_code("code123")
        assert token == "ghp_test"


@pytest.mark.asyncio
async def test_get_pr_changed_files():
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"filename": "src/pagination.py", "patch": "@@ -1,3 +1,5 @@\n def paginate"},
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mc

        files = await get_pr_changed_files("ghp_test", "owner", "repo", 42)
        assert files[0]["filename"] == "src/pagination.py"


def test_find_test_file_content_maps_correctly():
    changed = [
        {"filename": "src/pagination.py"},
        {"filename": "utils/helpers.py"},
    ]
    # Returns candidate test paths — we verify the mapping logic
    from integrations.github import _candidate_test_paths
    paths = _candidate_test_paths(changed)
    assert "tests/test_pagination.py" in paths
    assert "tests/test_helpers.py" in paths
```

**Step 2: Run to verify failure**

```bash
cd backend && python -m pytest tests/test_github_client.py -v
```
Expected: `ImportError`

**Step 3: Implement `backend/integrations/github.py`**

```python
"""GitHub OAuth client and REST API helpers."""

import re
import httpx
from config import settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"


def get_github_oauth_url(state: str) -> str:
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/github/callback"
    params = (
        f"client_id={settings.github_oauth_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo"
        f"&state={state}"
    )
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
        # e.g. src/foo/bar.py -> tests/test_bar.py AND src/foo/tests/test_bar.py
        basename = name.split("/")[-1]
        stem = basename.replace(".py", "").replace(".ts", "").replace(".js", "")
        candidates.append(f"tests/test_{stem}.py")
        candidates.append(f"tests/{stem}_test.py")
        candidates.append(f"__tests__/{stem}.test.ts")
        # same directory tests
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
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_github_client.py -v
```
Expected: all 4 tests PASS

**Step 5: Commit**

```bash
git add backend/integrations/github.py backend/tests/test_github_client.py
git commit -m "feat: add GitHub OAuth client and PR diff/test file helpers"
```

---

## Task 4: LLM Test Case Generator

**Files:**
- Create: `backend/integrations/generate.py`

**Step 1: Write the failing test**

Create `backend/tests/test_generate.py`:

```python
"""Unit tests for LLM-based test case generation (LLM calls mocked)."""
import pytest
from unittest.mock import patch, AsyncMock
from integrations.generate import parse_test_cases_from_file, generate_test_cases_from_diff


SAMPLE_PYTEST = """
def test_paginate_first_page():
    assert paginate([1,2,3,4,5], 1, 2) == [1, 2]

def test_paginate_last_page():
    assert paginate([1,2,3,4,5], 3, 2) == [5]

def test_paginate_returns_none_side_effect():
    result = set_flag(True)
    assert result is None
"""

MOCK_LLM_PARSE_RESPONSE = """
[
  {"input": "paginate([1,2,3,4,5], 1, 2)", "expected_output": "[1, 2]"},
  {"input": "paginate([1,2,3,4,5], 3, 2)", "expected_output": "[5]"},
  {"input": "set_flag(True)", "expected_output": "None"}
]
"""


@pytest.mark.asyncio
async def test_parse_test_cases_from_file():
    with patch("integrations.generate.LLM") as MockLLM:
        instance = MockLLM.return_value
        instance.complete = AsyncMock(return_value=MOCK_LLM_PARSE_RESPONSE)
        result = await parse_test_cases_from_file(SAMPLE_PYTEST)

    assert len(result) == 3
    assert result[0]["input"] == "paginate([1,2,3,4,5], 1, 2)"
    assert result[0]["expected_output"] == "[1, 2]"
    assert result[2]["expected_output"] == "None"


MOCK_LLM_GEN_RESPONSE = """
[
  {"input": "fix_pagination([1,2,3], 1, 2)", "expected_output": "[1, 2]"}
]
"""


@pytest.mark.asyncio
async def test_generate_test_cases_from_diff():
    with patch("integrations.generate.LLM") as MockLLM:
        instance = MockLLM.return_value
        instance.complete = AsyncMock(return_value=MOCK_LLM_GEN_RESPONSE)
        result = await generate_test_cases_from_diff(
            title="Fix pagination",
            description="Off by one error",
            diff_text="@@ def paginate",
        )

    assert len(result) == 1
    assert result[0]["input"] == "fix_pagination([1,2,3], 1, 2)"
```

**Step 2: Run to verify failure**

```bash
cd backend && python -m pytest tests/test_generate.py -v
```
Expected: `ImportError`

**Step 3: Implement `backend/integrations/generate.py`**

```python
"""LLM-based test case parsing and generation for interview challenges."""

import json
import re
import logging
from llm import LLM
from config import settings

logger = logging.getLogger(__name__)

_PARSE_SYSTEM = """You are a test case extractor. Given Python test code, extract each test assertion as a JSON array of objects with keys "input" and "expected_output".
- "input" must be a Python expression that calls the function under test (e.g. `foo(1, 2)`)
- "expected_output" must be a Python literal of the expected return value (e.g. `[1, 2]`, `"hello"`, `42`, `None`)
- For void functions (no return value / `assert result is None`), use `"None"` as expected_output
- Output ONLY valid JSON array, no markdown, no explanation."""

_GENERATE_SYSTEM = """You are a test case generator for coding challenges. Given a bug description and code diff, generate test cases as a JSON array of objects with keys "input" and "expected_output".
- "input": a Python function call expression
- "expected_output": the expected return value as a Python literal, or "None" for void functions
- Generate 3-5 meaningful test cases that cover the described bug and edge cases
- Output ONLY valid JSON array, no markdown, no explanation."""


def _extract_json(text: str) -> list[dict]:
    """Extract JSON array from LLM response, stripping any markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array")
    return [{"input": str(item["input"]), "expected_output": str(item["expected_output"])} for item in parsed]


async def parse_test_cases_from_file(test_file_content: str) -> list[dict]:
    """Parse existing pytest/unittest file into {input, expected_output} pairs."""
    llm = LLM(model=settings.default_model, system_prompt=_PARSE_SYSTEM)
    response = await llm.complete(
        f"Extract test cases from this test file:\n\n```python\n{test_file_content}\n```"
    )
    try:
        return _extract_json(response)
    except Exception as e:
        logger.warning("Failed to parse test cases from file: %s", e)
        return []


async def generate_test_cases_from_diff(title: str, description: str, diff_text: str) -> list[dict]:
    """Generate test cases from issue description and PR diff."""
    llm = LLM(model=settings.default_model, system_prompt=_GENERATE_SYSTEM)
    prompt = f"Issue: {title}\n\nDescription:\n{description}\n\nCode diff:\n```diff\n{diff_text}\n```"
    response = await llm.complete(prompt)
    try:
        return _extract_json(response)
    except Exception as e:
        logger.warning("Failed to generate test cases from diff: %s", e)
        return []


async def build_challenge_from_issue(
    issue: dict,
    changed_files: list[dict],
    test_file_contents: list[str],
) -> dict:
    """
    Given a Linear issue + GitHub PR data, return a populated challenge dict.
    Tries to use existing tests first; falls back to LLM generation.
    """
    title = issue.get("title", "")
    description = issue.get("description", "") or ""

    test_cases: list[dict] = []
    source = "llm_generated"

    # Try parsing existing test files first
    for test_content in test_file_contents:
        parsed = await parse_test_cases_from_file(test_content)
        test_cases.extend(parsed)
    if test_cases:
        source = "existing_tests"

    # Fall back to LLM generation from diff
    if not test_cases:
        diff_text = "\n".join(
            f"--- {f['filename']}\n{f.get('patch', '')}"
            for f in changed_files
        )
        test_cases = await generate_test_cases_from_diff(title, description, diff_text)

    # Infer starter code from changed file signatures (best effort)
    starter_code = _extract_stubs(changed_files)

    return {
        "title": title,
        "description": description,
        "starter_code": starter_code,
        "test_cases": test_cases,
        "source": source,
    }


def _extract_stubs(changed_files: list[dict]) -> str:
    """Extract function signatures from diff patches as stub starter code."""
    stubs = []
    for f in changed_files:
        patch = f.get("patch", "")
        for line in patch.splitlines():
            if line.startswith("+") and re.match(r"\+\s*def ", line):
                sig = line.lstrip("+").rstrip()
                stubs.append(sig)
                stubs.append("    pass")
                stubs.append("")
    return "\n".join(stubs).strip()
```

**Step 4: Check that `LLM` has a `complete` method**

```bash
cd backend && grep -n "async def complete\|def complete" llm.py
```

If `complete` doesn't exist, look for the equivalent (e.g. `stream` for streaming). If only `stream` exists, replace `llm.complete(prompt)` in `generate.py` with:

```python
full = ""
async for chunk in llm.stream(prompt):
    full += chunk
response = full
```

**Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_generate.py -v
```
Expected: all 2 tests PASS

**Step 6: Commit**

```bash
git add backend/integrations/generate.py backend/tests/test_generate.py
git commit -m "feat: add LLM test case parser and generator for Linear issues"
```

---

## Task 5: Integrations Router + Token Storage + Register in main.py

**Files:**
- Create: `backend/integrations/store.py`
- Create: `backend/integrations/router.py`
- Modify: `backend/main.py` (2 lines)

**Step 1: Write the failing test**

Create `backend/tests/test_integrations_router.py`:

```python
"""Integration router tests — OAuth callbacks and status endpoint."""
import pytest
from unittest.mock import patch, AsyncMock

# Uses conftest.py fixtures: auth_client (authenticated), client (unauthenticated)

@pytest.mark.asyncio
async def test_status_unauthenticated(client):
    resp = await client.get("/api/integrations/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_no_connections(auth_client):
    with patch("integrations.store.get_integration") as mock_get:
        mock_get.return_value = None
        resp = await auth_client.get("/api/integrations/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"linear": False, "github": False}


@pytest.mark.asyncio
async def test_status_with_linear_connected(auth_client):
    def side_effect(user_id, provider):
        return "tok_test" if provider == "linear" else None

    with patch("integrations.store.get_integration", side_effect=side_effect):
        resp = await auth_client.get("/api/integrations/status")
    assert resp.status_code == 200
    assert resp.json() == {"linear": True, "github": False}


@pytest.mark.asyncio
async def test_linear_issues_requires_auth(client):
    resp = await client.get("/api/integrations/linear/issues")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_linear_issues_requires_connection(auth_client):
    with patch("integrations.store.get_integration", return_value=None):
        resp = await auth_client.get("/api/integrations/linear/issues")
    assert resp.status_code == 400
    assert "not connected" in resp.json()["detail"].lower()
```

**Step 2: Run to verify failure**

```bash
cd backend && python -m pytest tests/test_integrations_router.py -v
```
Expected: `ImportError` or 404 (router not registered yet)

**Step 3: Create `backend/integrations/store.py`**

```python
"""Token storage for OAuth integrations using Supabase."""
import logging
from database import get_supabase_client

logger = logging.getLogger(__name__)


def get_integration(user_id: str, provider: str) -> str | None:
    """Return the stored access token for a provider, or None if not connected."""
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("user_integrations")
            .select("access_token")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["access_token"]
        return None
    except Exception as e:
        logger.error("get_integration error: %s", e)
        return None


def upsert_integration(user_id: str, provider: str, access_token: str, refresh_token: str | None = None) -> None:
    """Store or update an OAuth token for a provider."""
    supabase = get_supabase_client()
    if not supabase:
        raise RuntimeError("Supabase unavailable")
    supabase.table("user_integrations").upsert(
        {
            "user_id": user_id,
            "provider": provider,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "updated_at": "NOW()",
        },
        on_conflict="user_id,provider",
    ).execute()
```

**Step 4: Create `backend/integrations/router.py`**

```python
"""FastAPI router for Linear + GitHub OAuth and challenge generation."""
import hashlib
import hmac
import json
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from auth import get_current_user
from config import settings
from integrations import linear as linear_client
from integrations import github as github_client
from integrations import store
from integrations.generate import build_challenge_from_issue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# ---------------------------------------------------------------------------
# CSRF state helpers (sign user_id into state param)
# ---------------------------------------------------------------------------

_SECRET = settings.agent_internal_secret or "dev-secret"


def _make_state(user_id: str) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}:{nonce}"
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_state(state: str) -> str | None:
    """Verify state and return user_id, or None if invalid."""
    try:
        parts = state.rsplit(":", 2)
        if len(parts) != 3:
            return None
        user_id, nonce, sig = parts
        payload = f"{user_id}:{nonce}"
        expected = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return user_id
    except Exception:
        return None


_POPUP_CLOSE_HTML = """<!DOCTYPE html>
<html><body><script>
  window.opener && window.opener.postMessage({type: "oauth_success", provider: "%s"}, "*");
  window.close();
</script></body></html>"""

_POPUP_ERROR_HTML = """<!DOCTYPE html>
<html><body><p>OAuth failed: %s</p><script>
  window.opener && window.opener.postMessage({type: "oauth_error", provider: "%s", error: "%s"}, "*");
  window.close();
</script></body></html>"""

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_status(user_id: str = Depends(get_current_user)):
    return {
        "linear": store.get_integration(user_id, "linear") is not None,
        "github": store.get_integration(user_id, "github") is not None,
    }

# ---------------------------------------------------------------------------
# Linear OAuth
# ---------------------------------------------------------------------------

@router.get("/linear/connect")
async def linear_connect(user_id: str = Depends(get_current_user)):
    from fastapi.responses import RedirectResponse
    state = _make_state(user_id)
    url = linear_client.get_linear_oauth_url(state)
    return RedirectResponse(url)


@router.get("/linear/callback")
async def linear_callback(code: str = Query(...), state: str = Query(...)):
    user_id = _verify_state(state)
    if not user_id:
        return HTMLResponse(_POPUP_ERROR_HTML % ("linear", "linear", "Invalid state"), status_code=400)
    try:
        token = await linear_client.exchange_linear_code(code)
        store.upsert_integration(user_id, "linear", token)
        return HTMLResponse(_POPUP_CLOSE_HTML % "linear")
    except Exception as e:
        logger.error("Linear callback error: %s", e)
        return HTMLResponse(_POPUP_ERROR_HTML % ("linear", "linear", str(e)), status_code=500)

# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

@router.get("/github/connect")
async def github_connect(user_id: str = Depends(get_current_user)):
    from fastapi.responses import RedirectResponse
    state = _make_state(user_id)
    url = github_client.get_github_oauth_url(state)
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str = Query(...), state: str = Query(...)):
    user_id = _verify_state(state)
    if not user_id:
        return HTMLResponse(_POPUP_ERROR_HTML % ("github", "github", "Invalid state"), status_code=400)
    try:
        token = await github_client.exchange_github_code(code)
        store.upsert_integration(user_id, "github", token)
        return HTMLResponse(_POPUP_CLOSE_HTML % "github")
    except Exception as e:
        logger.error("GitHub callback error: %s", e)
        return HTMLResponse(_POPUP_ERROR_HTML % ("github", "github", str(e)), status_code=500)

# ---------------------------------------------------------------------------
# Linear issues list
# ---------------------------------------------------------------------------

@router.get("/linear/issues")
async def list_linear_issues(
    query: str = "",
    user_id: str = Depends(get_current_user),
):
    token = store.get_integration(user_id, "linear")
    if not token:
        raise HTTPException(status_code=400, detail="Linear not connected")
    issues = await linear_client.get_linear_issues(token, query=query)
    return issues

# ---------------------------------------------------------------------------
# Generate challenge from Linear issue
# ---------------------------------------------------------------------------

class GenerateChallengeRequest(BaseModel):
    issue_id: str


@router.post("/generate-challenge")
async def generate_challenge(
    req: GenerateChallengeRequest,
    user_id: str = Depends(get_current_user),
):
    linear_token = store.get_integration(user_id, "linear")
    if not linear_token:
        raise HTTPException(status_code=400, detail="Linear not connected")

    github_token = store.get_integration(user_id, "github")

    # Fetch Linear issue
    issue = await linear_client.get_linear_issue(linear_token, req.issue_id)

    changed_files: list[dict] = []
    test_file_contents: list[str] = []

    # If GitHub connected, fetch PR data
    if github_token:
        pr_urls = linear_client.get_github_pr_numbers_from_issue(issue)
        for pr_url in pr_urls[:1]:  # use first linked PR
            pr_info = await github_client.get_pr_info(github_token, pr_url)
            if pr_info:
                changed_files, test_file_contents, _ = pr_info
                break

    result = await build_challenge_from_issue(issue, changed_files, test_file_contents)
    return result
```

**Step 5: Register router in `backend/main.py`**

Find the line `from interviews import interview_router` (line ~81) and add after it:

```python
from integrations.router import router as integrations_router
```

Find `app.include_router(interview_router)` (line ~139) and add after it:

```python
app.include_router(integrations_router)
```

**Step 6: Fix the `hmac.new` typo** — it's `hmac.new(...)` in Python but the correct call is `hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()`. Actually in Python it's `hmac.new` — verify with:

```bash
cd backend && python -c "import hmac, hashlib; print(hmac.new(b'k', b'msg', hashlib.sha256).hexdigest())"
```

**Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_integrations_router.py -v
```
Expected: all 5 tests PASS

**Step 8: Commit**

```bash
git add backend/integrations/store.py backend/integrations/router.py backend/main.py backend/tests/test_integrations_router.py
git commit -m "feat: add integrations router with Linear/GitHub OAuth and generate-challenge endpoint"
```

---

## Task 6: Backend Test Suite Pass

**Files:**
- No new files — run full test suite

**Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: all tests PASS (including pre-existing ones)

**Step 2: Fix any failures**

Common issues:
- Import errors in `main.py` — check `integrations/router.py` imports resolve
- `hmac.new` → correct Python 3 call is `hmac.new(key, msg, digestmod)` ✓

**Step 3: Commit if any fixes needed**

```bash
git add -p
git commit -m "fix: resolve test suite issues after integrations module addition"
```

---

## Task 7: Frontend API Functions

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts` (add integration types)

**Step 1: Check existing types file**

```bash
cat frontend/lib/types.ts | grep -A5 "Interview"
```

**Step 2: Add types to `frontend/lib/types.ts`**

Add at the end of the file:

```typescript
// ---------------------------------------------------------------------------
// Integrations
// ---------------------------------------------------------------------------

export interface IntegrationStatus {
  linear: boolean;
  github: boolean;
}

export interface LinearIssue {
  id: string;
  identifier: string;
  title: string;
  description: string | null;
  branchName: string | null;
  url: string;
}

export interface GeneratedChallenge {
  title: string;
  description: string;
  starter_code: string;
  test_cases: Array<{ input: string; expected_output: string }>;
  source: "existing_tests" | "llm_generated";
}
```

**Step 3: Add API functions to `frontend/lib/api.ts`**

Add at the end of the file:

```typescript
// ---------------------------------------------------------------------------
// Integrations (Linear + GitHub)
// ---------------------------------------------------------------------------

export async function getIntegrationStatus(): Promise<IntegrationStatus> {
  return fetchJSON<IntegrationStatus>("/api/integrations/status");
}

export async function searchLinearIssues(query: string): Promise<LinearIssue[]> {
  const q = encodeURIComponent(query);
  return fetchJSON<LinearIssue[]>(`/api/integrations/linear/issues?query=${q}`);
}

export async function generateChallengeFromIssue(issueId: string): Promise<GeneratedChallenge> {
  return fetchJSON<GeneratedChallenge>("/api/integrations/generate-challenge", {
    method: "POST",
    body: JSON.stringify({ issue_id: issueId }),
  });
}
```

Also add the new types to the import at the top of `api.ts`:

```typescript
import type {
  // ... existing imports ...
  IntegrationStatus,
  LinearIssue,
  GeneratedChallenge,
} from "./types";
```

**Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

**Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/types.ts
git commit -m "feat: add frontend API functions and types for Linear/GitHub integration"
```

---

## Task 8: Frontend OAuth Hook + Connect Button

**Files:**
- Create: `frontend/hooks/useIntegrationStatus.ts`
- Create: `frontend/components/interview/OAuthConnectButton.tsx`

**Step 1: Create `frontend/hooks/useIntegrationStatus.ts`**

```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { getIntegrationStatus } from "@/lib/api";
import type { IntegrationStatus } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useIntegrationStatus() {
  const [status, setStatus] = useState<IntegrationStatus>({ linear: false, github: false });
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const s = await getIntegrationStatus();
      setStatus(s);
    } catch {
      // unauthenticated or error — keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connectProvider = useCallback(
    (provider: "linear" | "github"): Promise<void> => {
      return new Promise((resolve, reject) => {
        const url = `${API_BASE}/api/integrations/${provider}/connect`;
        const popup = window.open(url, `connect_${provider}`, "width=600,height=700");

        const handler = (event: MessageEvent) => {
          if (event.data?.type === "oauth_success" && event.data?.provider === provider) {
            window.removeEventListener("message", handler);
            refresh().then(resolve);
          } else if (event.data?.type === "oauth_error" && event.data?.provider === provider) {
            window.removeEventListener("message", handler);
            reject(new Error(event.data.error || "OAuth failed"));
          }
        };
        window.addEventListener("message", handler);

        // Fallback: if popup closes without postMessage
        const interval = setInterval(() => {
          if (popup?.closed) {
            clearInterval(interval);
            window.removeEventListener("message", handler);
            refresh().then(resolve).catch(reject);
          }
        }, 500);
      });
    },
    [refresh]
  );

  return { status, loading, refresh, connectProvider };
}
```

**Step 2: Create `frontend/components/interview/OAuthConnectButton.tsx`**

```tsx
"use client";

import { useState } from "react";
import { ExternalLink, CheckCircle, Loader2 } from "lucide-react";

interface Props {
  provider: "linear" | "github";
  connected: boolean;
  onConnect: () => Promise<void>;
  label: string;
}

export function OAuthConnectButton({ provider, connected, onConnect, label }: Props) {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setConnecting(true);
    setError(null);
    try {
      await onConnect();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConnecting(false);
    }
  };

  if (connected) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-500">
        <CheckCircle className="h-4 w-4" />
        {label} connected
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={handleClick}
        disabled={connecting}
        className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:border-accent hover:text-foreground text-muted transition-colors disabled:opacity-50 cursor-pointer"
      >
        {connecting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ExternalLink className="h-4 w-4" />
        )}
        Connect {label}
      </button>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

**Step 4: Commit**

```bash
git add frontend/hooks/useIntegrationStatus.ts frontend/components/interview/OAuthConnectButton.tsx
git commit -m "feat: add useIntegrationStatus hook and OAuthConnectButton component"
```

---

## Task 9: Linear Issue Picker Modal

**Files:**
- Create: `frontend/components/interview/LinearImportModal.tsx`

**Step 1: Implement `frontend/components/interview/LinearImportModal.tsx`**

```tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { Search, X, Loader2, ExternalLink, AlertCircle } from "lucide-react";
import { searchLinearIssues, generateChallengeFromIssue } from "@/lib/api";
import { OAuthConnectButton } from "./OAuthConnectButton";
import type { LinearIssue, GeneratedChallenge } from "@/lib/types";
import { useIntegrationStatus } from "@/hooks/useIntegrationStatus";

interface Props {
  onImport: (challenge: GeneratedChallenge) => void;
  onClose: () => void;
}

export function LinearImportModal({ onImport, onClose }: Props) {
  const { status, loading: statusLoading, connectProvider } = useIntegrationStatus();
  const [query, setQuery] = useState("");
  const [issues, setIssues] = useState<LinearIssue[]>([]);
  const [searching, setSearching] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null); // issue id being generated
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Auto-search when Linear is connected
  useEffect(() => {
    if (!status.linear) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setError(null);
      try {
        const results = await searchLinearIssues(query);
        setIssues(results);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, status.linear]);

  const handleSelect = async (issue: LinearIssue) => {
    setGenerating(issue.id);
    setError(null);
    try {
      const challenge = await generateChallengeFromIssue(issue.id);
      onImport(challenge);
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setGenerating(null);
    }
  };

  const needsLinear = !status.linear;
  const needsGitHub = status.linear && !status.github;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl border border-border bg-background shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Import from Linear</h2>
          <button onClick={onClose} className="text-muted hover:text-foreground cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Connect prompts */}
          {!statusLoading && needsLinear && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <p className="text-sm text-muted">Connect your Linear account to browse issues.</p>
              <OAuthConnectButton
                provider="linear"
                connected={false}
                onConnect={() => connectProvider("linear")}
                label="Linear"
              />
            </div>
          )}

          {!statusLoading && needsGitHub && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                <p className="text-sm text-muted">
                  Connect GitHub to auto-import test cases from linked PRs. You can skip this and test cases will be AI-generated.
                </p>
              </div>
              <OAuthConnectButton
                provider="github"
                connected={false}
                onConnect={() => connectProvider("github")}
                label="GitHub"
              />
            </div>
          )}

          {/* Search */}
          {status.linear && (
            <>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search issues…"
                  className="w-full rounded-lg border border-input-border bg-input pl-9 pr-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                  autoFocus
                />
              </div>

              {error && (
                <p className="text-xs text-red-400">{error}</p>
              )}

              {/* Issue list */}
              <div className="max-h-72 overflow-y-auto space-y-1">
                {searching && (
                  <div className="flex justify-center py-6">
                    <Loader2 className="h-5 w-5 animate-spin text-muted" />
                  </div>
                )}
                {!searching && issues.length === 0 && query && (
                  <p className="text-center text-sm text-muted py-6">No issues found</p>
                )}
                {!searching && issues.map((issue) => (
                  <button
                    key={issue.id}
                    onClick={() => handleSelect(issue)}
                    disabled={generating === issue.id}
                    className="w-full flex items-start gap-3 rounded-lg border border-border px-4 py-3 text-left hover:border-accent hover:bg-accent/5 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted font-mono shrink-0">{issue.identifier}</span>
                        <span className="text-sm font-medium truncate">{issue.title}</span>
                      </div>
                      {issue.description && (
                        <p className="text-xs text-muted mt-0.5 line-clamp-2">{issue.description}</p>
                      )}
                    </div>
                    {generating === issue.id ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted shrink-0 mt-0.5" />
                    ) : (
                      <ExternalLink className="h-3.5 w-3.5 text-muted shrink-0 mt-0.5" />
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

**Step 3: Commit**

```bash
git add frontend/components/interview/LinearImportModal.tsx
git commit -m "feat: add LinearImportModal component with issue search and OAuth prompts"
```

---

## Task 10: Wire Into Create Page

**Files:**
- Modify: `frontend/app/interview/create/page.tsx`

**Step 1: Add imports at the top of `create/page.tsx`**

After the existing imports, add:

```tsx
import { LinearImportModal } from "@/components/interview/LinearImportModal";
import type { GeneratedChallenge } from "@/lib/types";
```

**Step 2: Add modal state to the component**

In the component body, after `const [error, setError] = useState<string | null>(null);`, add:

```tsx
const [showLinearModal, setShowLinearModal] = useState(false);
```

**Step 3: Add the import handler**

After the `removeChallenge` function, add:

```tsx
const handleLinearImport = useCallback(
  (generated: GeneratedChallenge) => {
    updateChallenge(activeChallengeIdx, {
      title: generated.title,
      description: generated.description,
      starter_code: generated.starter_code,
      test_cases: generated.test_cases.length > 0
        ? generated.test_cases
        : [{ ...EMPTY_TEST_CASE }],
      category: "coding",
    });
  },
  [activeChallengeIdx, updateChallenge]
);
```

**Step 4: Add "Import from Linear" button in Step 2**

In the Step 2 render block, find:
```tsx
<div>
  <h2 className="text-lg font-semibold mb-1">
    Add Challenges
  </h2>
```

Replace with:

```tsx
<div className="flex items-start justify-between">
  <div>
    <h2 className="text-lg font-semibold mb-1">Add Challenges</h2>
    <p className="text-sm text-muted">
      Create the questions candidates will solve. For coding
      questions, add test cases.
    </p>
  </div>
  <button
    onClick={() => setShowLinearModal(true)}
    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-muted hover:text-foreground hover:border-accent transition-colors cursor-pointer shrink-0"
  >
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M3.5 19.5 15 8l-1.5-1.5L2 18zm16.5-12L11.5 16l1.5 1.5L21 9zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
    </svg>
    Import from Linear
  </button>
</div>
```

Remove the now-duplicate `<p>` tag that follows (the one starting "Create the questions...").

**Step 5: Add modal at the bottom of the return**

Before the final closing `</div>` of the component return, add:

```tsx
{showLinearModal && (
  <LinearImportModal
    onImport={handleLinearImport}
    onClose={() => setShowLinearModal(false)}
  />
)}
```

**Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

**Step 7: Smoke test manually**

```bash
cd frontend && npm run dev
```
Navigate to `http://localhost:3000/interview/create`, go to Step 2, verify "Import from Linear" button appears. Click it — modal should open with "Connect Linear" prompt.

**Step 8: Commit**

```bash
git add frontend/app/interview/create/page.tsx
git commit -m "feat: wire Linear import button and modal into interview create flow"
```

---

## Final: Re-enable Interview Mode

The interview router currently has `INTERVIEW_MODE_ENABLED = False`. This was a separate disable — confirm with the team before re-enabling. If ready:

In `backend/interviews/router.py`, set:
```python
INTERVIEW_MODE_ENABLED = True
```

And in `frontend/app/interview/layout.tsx`, remove any redirect/disabled guard added in the `disable-interview-mode` PR.

```bash
git add backend/interviews/router.py frontend/app/interview/layout.tsx
git commit -m "feat: re-enable interview mode"
```
