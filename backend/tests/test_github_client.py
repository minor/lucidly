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


def test_candidate_test_paths_maps_correctly():
    changed = [
        {"filename": "src/pagination.py"},
        {"filename": "utils/helpers.py"},
    ]
    from integrations.github import _candidate_test_paths
    paths = _candidate_test_paths(changed)
    assert "tests/test_pagination.py" in paths
    assert "tests/test_helpers.py" in paths
