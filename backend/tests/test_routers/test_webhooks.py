"""Tests for Strava webhook endpoints.

All Celery task dispatching is MOCKED — no real task execution.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /webhooks/strava — hub.challenge verification
# ---------------------------------------------------------------------------


class TestStravaWebhookVerify:
    """Tests for GET /webhooks/strava."""

    @patch("app.routers.webhooks.get_settings")
    async def test_valid_verification(self, mock_settings: MagicMock, client: AsyncClient) -> None:
        """Valid hub.challenge request should return the challenge."""
        mock_settings.return_value = MagicMock(STRAVA_VERIFY_TOKEN="test-verify-token")

        response = await client.get(
            "/webhooks/strava",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "abc123challenge",
                "hub.verify_token": "test-verify-token",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hub.challenge"] == "abc123challenge"

    @patch("app.routers.webhooks.get_settings")
    async def test_invalid_verify_token(
        self, mock_settings: MagicMock, client: AsyncClient
    ) -> None:
        """Invalid verify token should return 403."""
        mock_settings.return_value = MagicMock(STRAVA_VERIFY_TOKEN="correct-token")

        response = await client.get(
            "/webhooks/strava",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "abc123",
                "hub.verify_token": "wrong-token",
            },
        )

        assert response.status_code == 403

    @patch("app.routers.webhooks.get_settings")
    async def test_invalid_mode(self, mock_settings: MagicMock, client: AsyncClient) -> None:
        """Invalid hub.mode should return 400."""
        mock_settings.return_value = MagicMock(STRAVA_VERIFY_TOKEN="test-token")

        response = await client.get(
            "/webhooks/strava",
            params={
                "hub.mode": "unsubscribe",
                "hub.challenge": "abc123",
                "hub.verify_token": "test-token",
            },
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /webhooks/strava — event receiver
# ---------------------------------------------------------------------------


class TestStravaWebhookReceive:
    """Tests for POST /webhooks/strava."""

    @patch("app.services.strava_webhook_service.celery_app")
    async def test_valid_create_event(
        self, mock_celery: MagicMock, client: AsyncClient
    ) -> None:
        """Valid create activity event should queue task and return 200."""
        mock_task = MagicMock()
        mock_task.id = "task-uuid-123"
        mock_celery.send_task.return_value = mock_task

        event = {
            "object_type": "activity",
            "aspect_type": "create",
            "object_id": 12345,
            "owner_id": 67890,
        }

        response = await client.post("/webhooks/strava", json=event)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert data["task_id"] == "task-uuid-123"

    @patch("app.services.strava_webhook_service.celery_app")
    async def test_valid_update_event(
        self, mock_celery: MagicMock, client: AsyncClient
    ) -> None:
        """Valid update activity event should queue task."""
        mock_task = MagicMock()
        mock_task.id = "task-uuid-456"
        mock_celery.send_task.return_value = mock_task

        event = {
            "object_type": "activity",
            "aspect_type": "update",
            "object_id": 12345,
            "owner_id": 67890,
        }

        response = await client.post("/webhooks/strava", json=event)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-uuid-456"

    @patch("app.services.strava_webhook_service.celery_app")
    async def test_valid_delete_event(
        self, mock_celery: MagicMock, client: AsyncClient
    ) -> None:
        """Valid delete activity event should queue task."""
        mock_task = MagicMock()
        mock_task.id = "task-uuid-789"
        mock_celery.send_task.return_value = mock_task

        event = {
            "object_type": "activity",
            "aspect_type": "delete",
            "object_id": 12345,
            "owner_id": 67890,
        }

        response = await client.post("/webhooks/strava", json=event)

        assert response.status_code == 200

    async def test_athlete_event_ignored(self, client: AsyncClient) -> None:
        """Athlete events should be received but task_id should be null."""
        event = {
            "object_type": "athlete",
            "aspect_type": "update",
            "object_id": 67890,
            "owner_id": 67890,
        }

        response = await client.post("/webhooks/strava", json=event)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] is None

    async def test_missing_fields_returns_400(self, client: AsyncClient) -> None:
        """Webhook with missing required fields should return 400."""
        event = {
            "object_type": "activity",
            # Missing: aspect_type, object_id, owner_id
        }

        response = await client.post("/webhooks/strava", json=event)

        assert response.status_code == 400

    async def test_empty_body_returns_400(self, client: AsyncClient) -> None:
        """Empty or invalid JSON body should return 400."""
        response = await client.post(
            "/webhooks/strava",
            content=b"not json",
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 400
