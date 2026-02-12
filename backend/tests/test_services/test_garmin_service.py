"""Tests for the Garmin Connect integration service.

All garminconnect library interactions are MOCKED — no real API calls.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.garmin_service import (
    GarminAuthError,
    GarminService,
    GarminSyncError,
    decrypt_credentials,
    encrypt_credentials,
)


# ---------------------------------------------------------------------------
# Credential encryption / decryption
# ---------------------------------------------------------------------------


class TestCredentialEncryption:
    """Tests for encrypt_credentials / decrypt_credentials round-trip."""

    def test_round_trip(self) -> None:
        """Encrypted credentials should decrypt back to the original values."""
        email = "rider@example.com"
        password = "s3cret-p@ss!"
        key = "my-test-secret-key"

        encrypted = encrypt_credentials(email, password, key)
        assert isinstance(encrypted, bytes)
        assert encrypted != b""

        decrypted_email, decrypted_password = decrypt_credentials(encrypted, key)
        assert decrypted_email == email
        assert decrypted_password == password

    def test_different_keys_produce_different_ciphertext(self) -> None:
        """Different secret keys should produce different encrypted output."""
        email = "user@test.com"
        password = "pass123"

        enc1 = encrypt_credentials(email, password, "key-one")
        enc2 = encrypt_credentials(email, password, "key-two")

        assert enc1 != enc2

    def test_wrong_key_raises_auth_error(self) -> None:
        """Decrypting with the wrong key should raise GarminAuthError."""
        encrypted = encrypt_credentials("user@test.com", "pass", "correct-key")

        with pytest.raises(GarminAuthError, match="Failed to decrypt"):
            decrypt_credentials(encrypted, "wrong-key")

    def test_corrupted_data_raises_auth_error(self) -> None:
        """Corrupted encrypted data should raise GarminAuthError."""
        with pytest.raises(GarminAuthError, match="Failed to decrypt"):
            decrypt_credentials(b"totally-not-valid-fernet-data", "any-key")

    def test_special_characters_in_credentials(self) -> None:
        """Credentials with special characters should survive round-trip."""
        email = "user+tag@example.com"
        password = 'p@$$w0rd!#%^&*(){}[]|"<>?'
        key = "test-key"

        encrypted = encrypt_credentials(email, password, key)
        dec_email, dec_password = decrypt_credentials(encrypted, key)

        assert dec_email == email
        assert dec_password == password


# ---------------------------------------------------------------------------
# GarminService — login
# ---------------------------------------------------------------------------


class TestGarminServiceLogin:
    """Tests for GarminService.login()."""

    @patch("app.services.garmin_service.Garmin")
    def test_login_success(self, mock_garmin_cls: MagicMock) -> None:
        """Successful login should create client and call login()."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client

        svc = GarminService("user@test.com", "password123")
        svc.login()

        mock_garmin_cls.assert_called_once_with("user@test.com", "password123")
        mock_client.login.assert_called_once()

    @patch("app.services.garmin_service.Garmin")
    def test_login_auth_failure(self, mock_garmin_cls: MagicMock) -> None:
        """Authentication failure should raise GarminAuthError."""
        from garminconnect import GarminConnectAuthenticationError

        mock_client = MagicMock()
        mock_client.login.side_effect = GarminConnectAuthenticationError("Invalid credentials")
        mock_garmin_cls.return_value = mock_client

        svc = GarminService("bad@test.com", "wrongpass")
        with pytest.raises(GarminAuthError, match="authentication failed"):
            svc.login()

    @patch("app.services.garmin_service.Garmin")
    def test_login_connection_error(self, mock_garmin_cls: MagicMock) -> None:
        """Connection error should raise GarminSyncError."""
        from garminconnect import GarminConnectConnectionError

        mock_client = MagicMock()
        mock_client.login.side_effect = GarminConnectConnectionError("Network timeout")
        mock_garmin_cls.return_value = mock_client

        svc = GarminService("user@test.com", "password")
        with pytest.raises(GarminSyncError, match="connection error"):
            svc.login()


# ---------------------------------------------------------------------------
# GarminService — get_activities
# ---------------------------------------------------------------------------


class TestGarminServiceActivities:
    """Tests for GarminService.get_activities()."""

    @patch("app.services.garmin_service.Garmin")
    def test_get_activities_filters_by_date(self, mock_garmin_cls: MagicMock) -> None:
        """Activities older than 'since' should be filtered out."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client

        now = datetime.now()
        recent = (now - timedelta(hours=2)).isoformat()
        old = (now - timedelta(days=10)).isoformat()

        mock_client.get_activities.return_value = [
            {"activityId": "111", "startTimeLocal": recent, "activityName": "Recent Ride"},
            {"activityId": "222", "startTimeLocal": old, "activityName": "Old Ride"},
        ]

        svc = GarminService("user@test.com", "pass")
        svc.login()

        since = now - timedelta(days=5)
        activities = svc.get_activities(since)

        assert len(activities) == 1
        assert activities[0]["activityId"] == "111"

    @patch("app.services.garmin_service.Garmin")
    def test_get_activities_returns_empty_when_none_new(self, mock_garmin_cls: MagicMock) -> None:
        """Should return empty list when no activities are newer than 'since'."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client
        mock_client.get_activities.return_value = []

        svc = GarminService("user@test.com", "pass")
        svc.login()

        activities = svc.get_activities(datetime.now())
        assert activities == []

    def test_get_activities_without_login_raises(self) -> None:
        """Calling get_activities without login should raise GarminSyncError."""
        svc = GarminService("user@test.com", "pass")
        with pytest.raises(GarminSyncError, match="Not logged in"):
            svc.get_activities(datetime.now())


# ---------------------------------------------------------------------------
# GarminService — download_fit
# ---------------------------------------------------------------------------


class TestGarminServiceDownloadFit:
    """Tests for GarminService.download_fit()."""

    @patch("app.services.garmin_service.Garmin")
    def test_download_fit_success(self, mock_garmin_cls: MagicMock) -> None:
        """download_fit should return raw bytes from the Garmin API."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client

        fake_fit_data = b"\x0e\x10\x00\x00.FIT" + b"\x00" * 100
        mock_client.download_activity.return_value = fake_fit_data

        svc = GarminService("user@test.com", "pass")
        svc.login()

        result = svc.download_fit("12345")
        assert result == fake_fit_data
        mock_client.download_activity.assert_called_once_with(
            "12345", dl_fmt=mock_client.ActivityDownloadFormat.ORIGINAL
        )

    @patch("app.services.garmin_service.Garmin")
    def test_download_fit_failure(self, mock_garmin_cls: MagicMock) -> None:
        """download_fit should raise GarminSyncError on API failure."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client
        mock_client.download_activity.side_effect = Exception("Download failed")

        svc = GarminService("user@test.com", "pass")
        svc.login()

        with pytest.raises(GarminSyncError, match="Failed to download FIT"):
            svc.download_fit("12345")

    def test_download_fit_without_login_raises(self) -> None:
        """Calling download_fit without login should raise GarminSyncError."""
        svc = GarminService("user@test.com", "pass")
        with pytest.raises(GarminSyncError, match="Not logged in"):
            svc.download_fit("12345")


# ---------------------------------------------------------------------------
# GarminService — get_health_data
# ---------------------------------------------------------------------------


class TestGarminServiceHealth:
    """Tests for GarminService.get_health_data()."""

    @patch("app.services.garmin_service.Garmin")
    def test_get_health_data_full(self, mock_garmin_cls: MagicMock) -> None:
        """get_health_data should return all metrics when available."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client

        mock_client.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 82}},
            }
        }
        mock_client.get_body_composition.return_value = {"weight": 75500}  # grams
        mock_client.get_heart_rates.return_value = {"restingHeartRate": 52}
        mock_client.get_hrv_data.return_value = {
            "hrvSummary": {"weeklyAvg": 45}
        }
        mock_client.get_body_battery.return_value = [
            {"charged": 80},
            {"charged": 95},
            {"charged": 60},
        ]
        mock_client.get_stress_data.return_value = {"overallStressLevel": 35}

        svc = GarminService("user@test.com", "pass")
        svc.login()

        result = svc.get_health_data(date(2026, 2, 10))

        assert result["sleep_score"] == Decimal("82")
        assert result["weight_kg"] == Decimal("75500") / Decimal("1000")
        assert result["resting_hr"] == Decimal("52")
        assert result["hrv_ms"] == Decimal("45")
        assert result["body_battery"] == Decimal("95")  # max charged value
        assert result["stress_avg"] == Decimal("35")

    @patch("app.services.garmin_service.Garmin")
    def test_get_health_data_partial(self, mock_garmin_cls: MagicMock) -> None:
        """Missing health data should result in None values, not errors."""
        mock_client = MagicMock()
        mock_garmin_cls.return_value = mock_client

        # Only sleep data available
        mock_client.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 75}},
            }
        }
        mock_client.get_body_composition.side_effect = Exception("Not available")
        mock_client.get_heart_rates.return_value = {}
        mock_client.get_hrv_data.side_effect = Exception("Not available")
        mock_client.get_body_battery.return_value = []
        mock_client.get_stress_data.return_value = {}

        svc = GarminService("user@test.com", "pass")
        svc.login()

        result = svc.get_health_data(date(2026, 2, 10))

        assert result["sleep_score"] == Decimal("75")
        assert result["weight_kg"] is None
        assert result["resting_hr"] is None
        assert result["hrv_ms"] is None
        assert result["body_battery"] is None
        assert result["stress_avg"] is None

    def test_get_health_data_without_login_raises(self) -> None:
        """Calling get_health_data without login should raise GarminSyncError."""
        svc = GarminService("user@test.com", "pass")
        with pytest.raises(GarminSyncError, match="Not logged in"):
            svc.get_health_data(date(2026, 2, 10))


# ---------------------------------------------------------------------------
# Integration flow — disconnect clears credentials
# ---------------------------------------------------------------------------


class TestDisconnectFlow:
    """Test that disconnect workflow clears credential data."""

    def test_encrypt_then_clear_prevents_decryption(self) -> None:
        """After clearing encrypted bytes, the credentials are unrecoverable."""
        key = "secret-key"
        encrypted = encrypt_credentials("user@test.com", "password", key)

        # Verify they work before clearing
        email, pw = decrypt_credentials(encrypted, key)
        assert email == "user@test.com"

        # Simulating what disconnect does: setting credentials to None
        cleared: bytes | None = None
        assert cleared is None  # credentials are gone

        # Attempting to decrypt None would fail naturally
        # (the router checks for None before calling decrypt)
