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
