"""FastAPI router for Linear + GitHub OAuth and challenge generation."""
import hashlib
import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import httpx
from auth import get_current_user, _decode_token
from config import settings
from integrations import linear as linear_client
from integrations import github as github_client
from integrations import store
from integrations.generate import build_challenge_from_issue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# ---------------------------------------------------------------------------
# CSRF state helpers
# ---------------------------------------------------------------------------

_SECRET = (settings.agent_internal_secret or "dev-secret").encode()


def _make_state(user_id: str) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}:{nonce}"
    sig = hmac.HMAC(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_state(state: str) -> str | None:
    """Verify state and return user_id, or None if invalid."""
    try:
        # state = "user_id:nonce:sig"
        last_colon = state.rfind(":")
        second_last_colon = state.rfind(":", 0, last_colon)
        if second_last_colon == -1:
            return None
        user_id_nonce = state[:last_colon]
        sig = state[last_colon + 1:]
        user_id = state[:second_last_colon]
        expected = hmac.HMAC(_SECRET, user_id_nonce.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return user_id
    except Exception:
        return None


_POPUP_CLOSE_HTML = """<!DOCTYPE html>
<html><body><script>
  window.opener && window.opener.postMessage({{type: "oauth_success", provider: "{provider}"}}, document.referrer || "*");
  window.close();
</script></body></html>"""

_POPUP_ERROR_HTML = """<!DOCTYPE html>
<html><body><p>OAuth failed: {error}</p><script>
  window.opener && window.opener.postMessage({{type: "oauth_error", provider: "{provider}", error: "{error}"}}, document.referrer || "*");
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
async def linear_connect(token: str = Query(...)):
    """Redirect to Linear OAuth. Token passed as query param since this opens in a popup (no auth header)."""
    try:
        payload = await _decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    state = _make_state(user_id)
    url = linear_client.get_linear_oauth_url(state)
    return RedirectResponse(url)


@router.get("/linear/callback")
async def linear_callback(code: str = Query(...), state: str = Query(...)):
    user_id = _verify_state(state)
    if not user_id:
        return HTMLResponse(_POPUP_ERROR_HTML.format(provider="linear", error="Invalid state"), status_code=400)
    try:
        access_token, refresh_token = await linear_client.exchange_linear_code(code)
        store.upsert_integration(user_id, "linear", access_token, refresh_token)
        return HTMLResponse(_POPUP_CLOSE_HTML.format(provider="linear"))
    except Exception as e:
        logger.error("Linear callback error: %s", e)
        return HTMLResponse(_POPUP_ERROR_HTML.format(provider="linear", error=str(e)), status_code=500)

# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

@router.get("/github/connect")
async def github_connect(token: str = Query(...)):
    """Redirect to GitHub OAuth. Token passed as query param since this opens in a popup (no auth header)."""
    try:
        payload = await _decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    state = _make_state(user_id)
    url = github_client.get_github_oauth_url(state)
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str = Query(...), state: str = Query(...)):
    user_id = _verify_state(state)
    if not user_id:
        return HTMLResponse(_POPUP_ERROR_HTML.format(provider="github", error="Invalid state"), status_code=400)
    try:
        token = await github_client.exchange_github_code(code)
        store.upsert_integration(user_id, "github", token)
        return HTMLResponse(_POPUP_CLOSE_HTML.format(provider="github"))
    except Exception as e:
        logger.error("GitHub callback error: %s", e)
        return HTMLResponse(_POPUP_ERROR_HTML.format(provider="github", error=str(e)), status_code=500)

# ---------------------------------------------------------------------------
# Linear issues list
# ---------------------------------------------------------------------------

async def _get_fresh_linear_token(user_id: str) -> str:
    """Return a valid Linear access token, refreshing it if necessary."""
    token = store.get_integration(user_id, "linear")
    if not token:
        raise HTTPException(status_code=400, detail="Linear not connected")
    return token


async def _call_linear_with_refresh(user_id: str, fn, *args, **kwargs):
    """Call a Linear API function, auto-refreshing the token on 401."""
    token = await _get_fresh_linear_token(user_id)
    try:
        return await fn(token, *args, **kwargs)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise
    # Token expired — try to refresh
    refresh_token = store.get_refresh_token(user_id, "linear")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Linear token expired. Please reconnect.")
    new_access, new_refresh = await linear_client.refresh_linear_token(refresh_token)
    store.upsert_integration(user_id, "linear", new_access, new_refresh)
    return await fn(new_access, *args, **kwargs)


@router.get("/linear/issues")
async def list_linear_issues(
    query: str = "",
    user_id: str = Depends(get_current_user),
):
    issues = await _call_linear_with_refresh(user_id, linear_client.get_linear_issues, query=query)
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
    github_token = store.get_integration(user_id, "github")
    issue = await _call_linear_with_refresh(user_id, linear_client.get_linear_issue, req.issue_id)

    changed_files: list[dict] = []
    test_files: list[dict] = []
    ci_annotations: list[dict] = []
    base_source_files: list[dict] = []
    pr_owner: str | None = None
    pr_repo: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    is_merged: bool = False

    if github_token:
        pr_urls = linear_client.get_github_pr_urls_from_issue(issue)
        print(f"[generate-challenge] issue description: {repr(issue.get('description', '')[:300])}")
        print(f"[generate-challenge] PR URLs from issue: {pr_urls}")
        for pr_url in pr_urls[:1]:
            pr_info = await github_client.get_pr_info(github_token, pr_url)
            if pr_info:
                changed_files = pr_info["changed_files"]
                test_files = pr_info["test_files"]
                ci_annotations = pr_info["ci_annotations"]
                base_source_files = pr_info["base_source_files"]
                base_sha = pr_info["base_sha"]
                head_sha = pr_info["head_sha"]
                is_merged = pr_info["is_merged"]
                parsed = github_client._parse_pr_url(pr_url)
                if parsed:
                    pr_owner, pr_repo, _ = parsed
                print(
                    f"[generate-challenge] is_merged={is_merged} "
                    f"changed_files={[f['filename'] for f in changed_files]} "
                    f"test_files={len(test_files)} "
                    f"ci_annotations={len(ci_annotations)} "
                    f"base_source={len(base_source_files)}"
                )
                break
    else:
        print("[generate-challenge] No GitHub token — skipping PR fetch")

    result = await build_challenge_from_issue(
        issue,
        changed_files,
        test_files,
        ci_annotations,
        base_source_files,
        user_id=user_id,
        pr_owner=pr_owner,
        pr_repo=pr_repo,
        base_sha=base_sha,
        head_sha=head_sha,
        is_merged=is_merged,
    )
    return result
