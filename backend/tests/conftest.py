"""Shared fixtures for backend API tests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from config import limiter
from auth import get_current_user
from main import app

MOCK_USER_ID = "test|user123"


async def _mock_current_user() -> str:
    return MOCK_USER_ID


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset rate-limiter storage and dependency overrides between tests."""
    fresh = MemoryStorage()
    limiter._storage = fresh
    limiter._limiter = FixedWindowRateLimiter(fresh)
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    """Unauthenticated async HTTP client against the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client():
    """Authenticated async HTTP client (mocks get_current_user)."""
    app.dependency_overrides[get_current_user] = _mock_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
