"""Smoke tests for the health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /health should return 200 with expected keys."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "database" in body
    assert "redis" in body
    assert "disk_free_gb" in body


@pytest.mark.asyncio
async def test_health_disk_free_is_numeric(client: AsyncClient) -> None:
    """disk_free_gb should be a number."""
    response = await client.get("/health")
    body = response.json()
    assert isinstance(body["disk_free_gb"], (int, float))
    assert body["disk_free_gb"] >= 0
