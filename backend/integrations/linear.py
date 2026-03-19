"""Linear OAuth client and API helpers."""

import httpx
import urllib.parse
from config import settings

LINEAR_AUTHORIZE_URL = "https://linear.app/oauth/authorize"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_API_URL = "https://api.linear.app/graphql"


def get_linear_oauth_url(state: str) -> str:
    redirect_uri = f"{settings.integration_redirect_base_url}/api/integrations/linear/callback"
    params = urllib.parse.urlencode({
        "client_id": settings.linear_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read",
        "state": state,
    })
    return f"{LINEAR_AUTHORIZE_URL}?{params}"


async def exchange_linear_code(code: str) -> tuple[str, str | None]:
    """Exchange authorization code for (access_token, refresh_token)."""
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
        data = resp.json()
        return data["access_token"], data.get("refresh_token")


async def refresh_linear_token(refresh_token: str) -> tuple[str, str | None]:
    """Exchange a refresh token for a new (access_token, refresh_token)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LINEAR_TOKEN_URL,
            data={
                "client_id": settings.linear_client_id,
                "client_secret": settings.linear_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"], data.get("refresh_token")


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


def get_github_pr_urls_from_issue(issue: dict) -> list[str]:
    """Extract GitHub PR URLs from Linear issue attachments and description text."""
    import re
    pr_urls = []

    # Attachments (set by Linear-GitHub integration auto-linking)
    attachments = issue.get("attachments", {}).get("nodes", [])
    for att in attachments:
        url = att.get("url", "")
        if "/pull/" in url and "github.com" in url:
            pr_urls.append(url)

    # Fallback: scan description text for GitHub PR URLs (handles bare URLs and [text](<url>) format)
    description = issue.get("description") or ""
    for match in re.finditer(r"https://github\.com/[^\s\)>\]]+/pull/\d+", description):
        url = match.group(0).rstrip(".,;")
        if url not in pr_urls:
            pr_urls.append(url)

    return pr_urls
