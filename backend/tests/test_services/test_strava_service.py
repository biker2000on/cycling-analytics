"""Tests for the Strava integration service.

All Strava API interactions are MOCKED — no real API calls.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.strava_service import (
    STRAVA_AUTH_URL,
    StravaAuthError,
    StravaService,
    StravaSyncError,
    decrypt_token,
    encrypt_token,
)


# ---------------------------------------------------------------------------
# Token encryption / decryption
# ---------------------------------------------------------------------------


class TestTokenEncryption:
    """Tests for encrypt_token / decrypt_token round-trip."""

    def test_round_trip(self) -> None:
        """Encrypted token should decrypt back to the original value."""
        token = "abc123_access_token_value"
        key = "my-test-secret-key"

        encrypted = encrypt_token(token, key)
        assert isinstance(encrypted, bytes)
        assert encrypted != b""

        decrypted = decrypt_token(encrypted, key)
        assert decrypted == token

    def test_different_keys_produce_different_ciphertext(self) -> None:
        """Different secret keys should produce different encrypted output."""
        token = "some-token-value"

        enc1 = encrypt_token(token, "key-one")
        enc2 = encrypt_token(token, "key-two")

        assert enc1 != enc2

    def test_wrong_key_raises_auth_error(self) -> None:
        """Decrypting with the wrong key should raise StravaAuthError."""
        encrypted = encrypt_token("my-token", "correct-key")

        with pytest.raises(StravaAuthError, match="Failed to decrypt"):
            decrypt_token(encrypted, "wrong-key")

    def test_corrupted_data_raises_auth_error(self) -> None:
        """Corrupted encrypted data should raise StravaAuthError."""
        with pytest.raises(StravaAuthError, match="Failed to decrypt"):
            decrypt_token(b"totally-not-valid-fernet-data", "any-key")

    def test_special_characters_in_token(self) -> None:
        """Tokens with special characters should survive round-trip."""
        token = 'abc!@#$%^&*(){}[]|"<>?/+=_-'
        key = "test-key"

        encrypted = encrypt_token(token, key)
        decrypted = decrypt_token(encrypted, key)
        assert decrypted == token


# ---------------------------------------------------------------------------
# StravaService — build_auth_url
# ---------------------------------------------------------------------------


class TestBuildAuthUrl:
    """Tests for StravaService.build_auth_url()."""

    @patch("app.services.strava_service.get_settings")
    def test_build_auth_url_contains_required_params(self, mock_settings: MagicMock) -> None:
        """Auth URL should contain client_id, redirect_uri, response_type, scope."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
            STRAVA_CLIENT_SECRET="secret",
        )

        svc = StravaService()
        url = svc.build_auth_url("http://localhost:8000/callback")
        svc.close()

        assert STRAVA_AUTH_URL in url
        assert "client_id=12345" in url
        assert "redirect_uri=http" in url
        assert "response_type=code" in url
        assert "scope=read" in url

    @patch("app.services.strava_service.get_settings")
    def test_build_auth_url_uses_provided_redirect(self, mock_settings: MagicMock) -> None:
        """Auth URL should use the provided redirect_uri."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
        )

        svc = StravaService()
        url = svc.build_auth_url("https://myapp.com/strava/callback")
        svc.close()

        assert "myapp.com" in url


# ---------------------------------------------------------------------------
# StravaService — exchange_code
# ---------------------------------------------------------------------------


class TestExchangeCode:
    """Tests for StravaService.exchange_code()."""

    @patch("app.services.strava_service.get_settings")
    def test_exchange_code_success(self, mock_settings: MagicMock) -> None:
        """Successful code exchange should return token data."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
            STRAVA_CLIENT_SECRET="secret",
        )

        token_response = {
            "access_token": "at_abc123",
            "refresh_token": "rt_def456",
            "expires_at": 1700000000,
            "athlete": {"id": 999, "firstname": "Test", "lastname": "Rider"},
        }

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=token_response)
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.exchange_code("auth_code_xyz", "http://localhost:8000/callback")
        svc.close()

        assert result["access_token"] == "at_abc123"
        assert result["refresh_token"] == "rt_def456"
        assert result["athlete"]["id"] == 999

    @patch("app.services.strava_service.get_settings")
    def test_exchange_code_failure(self, mock_settings: MagicMock) -> None:
        """Failed code exchange should raise StravaAuthError."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
            STRAVA_CLIENT_SECRET="secret",
        )

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"message": "Bad Request"})
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        with pytest.raises(StravaAuthError, match="token exchange failed"):
            svc.exchange_code("bad_code", "http://localhost:8000/callback")
        svc.close()


# ---------------------------------------------------------------------------
# StravaService — refresh_tokens
# ---------------------------------------------------------------------------


class TestRefreshTokens:
    """Tests for StravaService.refresh_tokens()."""

    @patch("app.services.strava_service.get_settings")
    def test_refresh_tokens_success(self, mock_settings: MagicMock) -> None:
        """Successful token refresh should return new tokens."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
            STRAVA_CLIENT_SECRET="secret",
        )

        refresh_response = {
            "access_token": "new_at_abc",
            "refresh_token": "new_rt_def",
            "expires_at": 1700100000,
        }

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=refresh_response)
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.refresh_tokens("old_refresh_token")
        svc.close()

        assert result["access_token"] == "new_at_abc"
        assert result["refresh_token"] == "new_rt_def"
        assert result["expires_at"] == 1700100000

    @patch("app.services.strava_service.get_settings")
    def test_refresh_tokens_failure(self, mock_settings: MagicMock) -> None:
        """Failed token refresh should raise StravaAuthError."""
        mock_settings.return_value = MagicMock(
            STRAVA_CLIENT_ID="12345",
            STRAVA_CLIENT_SECRET="secret",
        )

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"message": "Unauthorized"})
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        with pytest.raises(StravaAuthError, match="token refresh failed"):
            svc.refresh_tokens("bad_refresh_token")
        svc.close()


# ---------------------------------------------------------------------------
# StravaService — get_athlete_info
# ---------------------------------------------------------------------------


class TestGetAthleteInfo:
    """Tests for StravaService.get_athlete_info()."""

    def test_get_athlete_info_success(self) -> None:
        """Successful athlete info fetch should return profile data."""
        athlete_data = {
            "id": 12345,
            "firstname": "Test",
            "lastname": "Rider",
            "city": "Portland",
        }

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=athlete_data)
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.get_athlete_info("valid_access_token")
        svc.close()

        assert result["id"] == 12345
        assert result["firstname"] == "Test"

    def test_get_athlete_info_unauthorized(self) -> None:
        """Unauthorized request should raise StravaAuthError."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"message": "Unauthorized"})
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        with pytest.raises(StravaAuthError, match="Failed to fetch athlete info"):
            svc.get_athlete_info("bad_token")
        svc.close()


# ---------------------------------------------------------------------------
# StravaService — fetch_activities_since
# ---------------------------------------------------------------------------


class TestFetchActivities:
    """Tests for StravaService.fetch_activities_since()."""

    def test_fetch_activities_returns_list(self) -> None:
        """Should return a list of activity summaries."""
        activities = [
            {"id": 1001, "name": "Morning Ride", "type": "Ride"},
            {"id": 1002, "name": "Afternoon Run", "type": "Run"},
        ]

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=activities)
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.fetch_activities_since("token", after_epoch=1000000, page=1)
        svc.close()

        assert len(result) == 2
        assert result[0]["name"] == "Morning Ride"

    def test_fetch_activities_empty(self) -> None:
        """Should return empty list when no activities."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=[])
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.fetch_activities_since("token", after_epoch=9999999999)
        svc.close()

        assert result == []

    def test_fetch_activities_api_error(self) -> None:
        """API error should raise StravaSyncError."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(500, json={"message": "Server Error"})
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        with pytest.raises(StravaSyncError, match="Failed to fetch activities"):
            svc.fetch_activities_since("token", after_epoch=0)
        svc.close()


# ---------------------------------------------------------------------------
# StravaService — fetch_activity_streams
# ---------------------------------------------------------------------------


class TestFetchStreams:
    """Tests for StravaService.fetch_activity_streams()."""

    def test_fetch_streams_success(self) -> None:
        """Should return streams keyed by type."""
        streams = {
            "time": {"data": [0, 1, 2, 3]},
            "watts": {"data": [200, 210, 205, 195]},
            "heartrate": {"data": [140, 142, 145, 143]},
        }

        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=streams)
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.fetch_activity_streams("token", 1001)
        svc.close()

        assert "time" in result
        assert result["watts"]["data"] == [200, 210, 205, 195]

    def test_fetch_streams_404_returns_empty(self) -> None:
        """404 (no streams) should return empty dict, not raise."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(404, json={"message": "Not Found"})
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.fetch_activity_streams("token", 9999)
        svc.close()

        assert result == {}


# ---------------------------------------------------------------------------
# StravaService — convert_strava_to_internal
# ---------------------------------------------------------------------------


class TestConvertStravaToInternal:
    """Tests for StravaService.convert_strava_to_internal()."""

    def test_basic_conversion(self) -> None:
        """Should map Strava fields to internal format."""
        strava_activity = {
            "id": 12345,
            "name": "Morning Ride",
            "sport_type": "Ride",
            "start_date": "2026-02-10T08:00:00Z",
            "elapsed_time": 3600,
            "distance": 32000.5,
            "total_elevation_gain": 450.2,
            "average_watts": 220,
            "max_watts": 550,
            "average_heartrate": 145,
            "max_heartrate": 178,
            "average_cadence": 85,
            "calories": 800,
            "device_name": "Garmin Edge 540",
        }

        activity_data, stream_records = StravaService.convert_strava_to_internal(
            strava_activity, {}
        )

        assert activity_data["external_id"] == "12345"
        assert activity_data["name"] == "Morning Ride"
        assert activity_data["sport_type"] == "Ride"
        assert activity_data["duration_seconds"] == 3600
        assert activity_data["distance_meters"] == Decimal("32000.5")
        assert activity_data["elevation_gain_meters"] == Decimal("450.2")
        assert activity_data["avg_power_watts"] == Decimal("220")
        assert activity_data["max_power_watts"] == Decimal("550")
        assert activity_data["avg_hr"] == 145
        assert activity_data["max_hr"] == 178
        assert activity_data["avg_cadence"] == 85
        assert activity_data["calories"] == 800
        assert stream_records == []

    def test_conversion_with_streams(self) -> None:
        """Should produce stream records from Strava streams."""
        strava_activity = {
            "id": 12345,
            "name": "Ride",
            "start_date": "2026-02-10T08:00:00Z",
            "elapsed_time": 4,
        }

        streams = {
            "time": {"data": [0, 1, 2, 3]},
            "watts": {"data": [200, 210, 205, 195]},
            "heartrate": {"data": [140, 142, 145, 143]},
            "latlng": {"data": [[45.5, -122.6], [45.501, -122.601], None, [45.503, -122.603]]},
            "altitude": {"data": [100.0, 100.5, 101.0, 101.5]},
        }

        activity_data, stream_records = StravaService.convert_strava_to_internal(
            strava_activity, streams
        )

        assert len(stream_records) == 4
        assert stream_records[0]["power_watts"] == 200
        assert stream_records[0]["heart_rate"] == 140
        assert stream_records[0]["elapsed_seconds"] == 0
        assert stream_records[0]["altitude_meters"] == Decimal("100.0")
        # GPS: latlng[0] = [45.5, -122.6] → POINT(-122.6 45.5)
        assert "POINT(-122.6 45.5)" in stream_records[0]["position"]
        # Third record has None latlng
        assert stream_records[2]["position"] is None

    def test_conversion_missing_power(self) -> None:
        """Activities without power data should have None for power fields."""
        strava_activity = {
            "id": 12345,
            "name": "Easy Run",
            "start_date": "2026-02-10T10:00:00Z",
            "elapsed_time": 1800,
            "distance": 5000,
        }

        activity_data, _ = StravaService.convert_strava_to_internal(strava_activity, {})

        assert activity_data["avg_power_watts"] is None
        assert activity_data["max_power_watts"] is None

    def test_conversion_bad_date_uses_utcnow(self) -> None:
        """Invalid start_date should fall back to UTC now."""
        strava_activity = {
            "id": 12345,
            "name": "Ride",
            "start_date": "not-a-date",
        }

        activity_data, _ = StravaService.convert_strava_to_internal(strava_activity, {})

        # Should be close to now (within a minute)
        assert (datetime.now(UTC) - activity_data["activity_date"]).total_seconds() < 60


# ---------------------------------------------------------------------------
# StravaService — backfill_all_activities
# ---------------------------------------------------------------------------


class TestBackfillAllActivities:
    """Tests for StravaService.backfill_all_activities()."""

    def test_backfill_paginates(self) -> None:
        """Should fetch multiple pages until empty."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First page: full page (100 items)
                return httpx.Response(200, json=[{"id": i} for i in range(100)])
            elif call_count == 2:
                # Second page: partial (signals end)
                return httpx.Response(200, json=[{"id": i + 100} for i in range(50)])
            return httpx.Response(200, json=[])

        mock_transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.backfill_all_activities("token")
        svc.close()

        assert len(result) == 150
        assert call_count == 2

    def test_backfill_empty_account(self) -> None:
        """Empty account should return empty list."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=[])
        )
        client = httpx.Client(transport=mock_transport)

        svc = StravaService(http_client=client)
        result = svc.backfill_all_activities("token")
        svc.close()

        assert result == []
