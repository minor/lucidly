"""FastAPI router for Linear + GitHub OAuth and challenge generation."""
import hashlib
import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

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
        token = await linear_client.exchange_linear_code(code)
        store.upsert_integration(user_id, "linear", token)
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

    issue = await linear_client.get_linear_issue(linear_token, req.issue_id)

    changed_files: list[dict] = []
    test_file_contents: list[str] = []

    if github_token:
        pr_urls = linear_client.get_github_pr_urls_from_issue(issue)
        for pr_url in pr_urls[:1]:
            pr_info = await github_client.get_pr_info(github_token, pr_url)
            if pr_info:
                changed_files, test_file_contents, _ = pr_info
                break

    result = await build_challenge_from_issue(issue, changed_files, test_file_contents)
    return result
