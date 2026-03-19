"""Integration router tests — OAuth callbacks and status endpoint."""
import pytest
from unittest.mock import patch

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
