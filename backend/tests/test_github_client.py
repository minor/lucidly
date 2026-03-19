"""Unit tests for GitHub API client (all HTTP calls mocked)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.github import (
    get_github_oauth_url,
    exchange_github_code,
    get_pr_changed_files,
    get_all_test_files,
    _is_test_file,
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


def test_is_test_file():
    assert _is_test_file("tests/test_pagination.py")
    assert _is_test_file("tests/pagination_test.py")
    assert _is_test_file("__tests__/pagination.test.ts")
    assert not _is_test_file("src/pagination.py")
    assert not _is_test_file(".github/workflows/test.yaml")


@pytest.mark.asyncio
async def test_get_all_test_files_returns_path_content_dicts():
    """get_all_test_files now returns [{path, content}] dicts."""
    dir_resp = MagicMock()
    dir_resp.status_code = 200
    dir_resp.raise_for_status = MagicMock()
    dir_resp.json.return_value = [
        {"type": "file", "path": "tests/test_foo.py"},
    ]
    file_resp = MagicMock()
    file_resp.status_code = 200
    file_resp.raise_for_status = MagicMock()
    file_resp.text = "def test_foo(): assert True"

    with patch("httpx.AsyncClient") as mock_cls:
        mc = AsyncMock()
        mc.__aenter__ = AsyncMock(return_value=mc)
        mc.__aexit__ = AsyncMock(return_value=False)
        mc.get = AsyncMock(side_effect=[dir_resp, MagicMock(status_code=404, raise_for_status=MagicMock()), MagicMock(status_code=404, raise_for_status=MagicMock())])
        mock_cls.return_value = mc

        with patch("integrations.github.get_file_content", new_callable=AsyncMock) as mock_fc:
            mock_fc.return_value = "def test_foo(): assert True"
            result = await get_all_test_files("ghp_test", "owner", "repo")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["path"] == "tests/test_foo.py"
    assert result[0]["content"] == "def test_foo(): assert True"
