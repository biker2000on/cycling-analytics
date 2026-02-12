"""Tests for integration router — configurable backfill days and Strava OAuth redirect."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.integration import IntegrationProvider, IntegrationStatus


def _mock_integration(
    provider: IntegrationProvider,
    status: IntegrationStatus = IntegrationStatus.active,
) -> MagicMock:
    integration = MagicMock()
    integration.id = 1
    integration.user_id = 1
    integration.provider = provider
    integration.status = status
    integration.credentials_encrypted = b"encrypted"
    integration.access_token_encrypted = b"encrypted"
    integration.refresh_token_encrypted = b"encrypted"
    integration.token_expires_at = None
    integration.athlete_id = "12345"
    integration.sync_enabled = True
    integration.error_message = None
    integration.last_sync_at = None
    return integration


def _mock_db_returning(value: MagicMock | None) -> AsyncMock:
    """Create a mock async DB session that returns ``value`` for scalar_one_or_none."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = value
    db.execute.return_value = result_mock
    return db


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    return create_app()


# ---------------------------------------------------------------------------
# Garmin sync — days parameter
# ---------------------------------------------------------------------------


class TestGarminSyncDays:
    """Test configurable days param on Garmin sync endpoint."""

    @pytest.mark.asyncio
    async def test_garmin_sync_default_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """POST /integrations/garmin/sync without days uses default 30."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/sync")

            assert resp.status_code == 202
            # First send_task call is activity sync — should have kwargs with days=30
            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 30}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_garmin_sync_custom_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """POST /integrations/garmin/sync?days=60 passes 60 to Celery."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/sync?days=60")

            assert resp.status_code == 202
            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 60}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_garmin_sync_days_validation_too_low(self, app) -> None:  # type: ignore[no-untyped-def]
        """days=0 should fail validation (ge=1)."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/sync?days=0")

            assert resp.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_garmin_sync_days_validation_too_high(self, app) -> None:  # type: ignore[no-untyped-def]
        """days=5000 should fail validation (le=3650)."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/sync?days=5000")

            assert resp.status_code == 422

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Garmin backfill endpoint
# ---------------------------------------------------------------------------


class TestGarminBackfill:
    """Test POST /integrations/garmin/backfill endpoint."""

    @pytest.mark.asyncio
    async def test_garmin_backfill_default_90_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """Garmin backfill defaults to 90 days."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-456")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/backfill")

            assert resp.status_code == 202
            data = resp.json()
            assert data["task_id"] == "task-456"
            assert "90 days" in data["message"]

            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 90}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_garmin_backfill_custom_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """Garmin backfill accepts custom days parameter."""
        integration = _mock_integration(IntegrationProvider.garmin)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-456")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/garmin/backfill?days=365")

            assert resp.status_code == 202
            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 365}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_garmin_backfill_no_integration_404(self, app) -> None:  # type: ignore[no-untyped-def]
        """Garmin backfill returns 404 when no integration exists."""

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(None)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/integrations/garmin/backfill")

        assert resp.status_code == 404

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Strava callback — redirect vs JSON
# ---------------------------------------------------------------------------


class TestStravaCallbackRedirect:
    """Test Strava OAuth callback redirect behavior."""

    @pytest.mark.asyncio
    async def test_strava_callback_redirects_by_default(self, app) -> None:  # type: ignore[no-untyped-def]
        """Default callback should return a 307 redirect to frontend."""
        integration = _mock_integration(IntegrationProvider.strava)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        mock_token_data = {
            "access_token": "at_123",
            "refresh_token": "rt_123",
            "expires_at": 9999999999,
            "athlete": {"id": 42},
        }

        with (
            patch("app.routers.integrations.StravaService") as mock_svc_cls,
            patch("app.routers.integrations.encrypt_token", return_value=b"enc"),
        ):
            mock_svc = MagicMock()
            mock_svc.exchange_code.return_value = mock_token_data
            mock_svc_cls.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as ac:
                resp = await ac.get("/integrations/strava/callback?code=test_code")

            assert resp.status_code == 307
            location = resp.headers["location"]
            assert "strava_connected=true" in location
            assert "athlete_id=42" in location

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_strava_callback_json_format(self, app) -> None:  # type: ignore[no-untyped-def]
        """format=json should return JSON response."""
        integration = _mock_integration(IntegrationProvider.strava)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        mock_token_data = {
            "access_token": "at_123",
            "refresh_token": "rt_123",
            "expires_at": 9999999999,
            "athlete": {"id": 42},
        }

        with (
            patch("app.routers.integrations.StravaService") as mock_svc_cls,
            patch("app.routers.integrations.encrypt_token", return_value=b"enc"),
        ):
            mock_svc = MagicMock()
            mock_svc.exchange_code.return_value = mock_token_data
            mock_svc_cls.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(
                    "/integrations/strava/callback?code=test_code&format=json"
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["athlete_id"] == "42"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_strava_callback_error_redirects(self, app) -> None:  # type: ignore[no-untyped-def]
        """Auth failure without format=json redirects with error param."""
        from app.services.strava_service import StravaAuthError

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(None)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.StravaService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.exchange_code.side_effect = StravaAuthError("bad code")
            mock_svc_cls.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as ac:
                resp = await ac.get("/integrations/strava/callback?code=bad_code")

            assert resp.status_code == 307
            location = resp.headers["location"]
            assert "strava_error=auth_failed" in location

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_strava_callback_error_json_raises_401(self, app) -> None:  # type: ignore[no-untyped-def]
        """Auth failure with format=json should raise 401."""
        from app.services.strava_service import StravaAuthError

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(None)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.StravaService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.exchange_code.side_effect = StravaAuthError("bad code")
            mock_svc_cls.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(
                    "/integrations/strava/callback?code=bad_code&format=json"
                )

            assert resp.status_code == 401

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Strava backfill — days parameter
# ---------------------------------------------------------------------------


class TestStravaBackfillDays:
    """Test configurable days param on Strava backfill endpoint."""

    @pytest.mark.asyncio
    async def test_strava_backfill_default_90_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """POST /integrations/strava/backfill without days uses default 90."""
        integration = _mock_integration(IntegrationProvider.strava)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-789")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/strava/backfill")

            assert resp.status_code == 202
            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 90}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_strava_backfill_custom_days(self, app) -> None:  # type: ignore[no-untyped-def]
        """POST /integrations/strava/backfill?days=365 passes 365."""
        integration = _mock_integration(IntegrationProvider.strava)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.integrations.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-789")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/integrations/strava/backfill?days=365")

            assert resp.status_code == 202
            call_args = mock_celery.send_task.call_args_list[0]
            assert call_args.kwargs.get("kwargs") == {"backfill_days": 365}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_strava_backfill_days_validation(self, app) -> None:  # type: ignore[no-untyped-def]
        """days=0 should fail validation."""
        integration = _mock_integration(IntegrationProvider.strava)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_returning(integration)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/integrations/strava/backfill?days=0")

        assert resp.status_code == 422

        app.dependency_overrides.clear()
