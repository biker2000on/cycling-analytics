"""Shared pytest fixtures for the cycling-analytics backend."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Return a Settings instance using defaults (no live services required)."""
    return Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5433/test_cycling",
        SYNC_DATABASE_URL="postgresql+psycopg2://test:test@localhost:5433/test_cycling",
        REDIS_URL="redis://localhost:6379/15",
        DEBUG=True,
    )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP test client bound to the FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
