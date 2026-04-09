"""Garmin Connect integration service.

Handles authentication, activity download, health data retrieval,
and credential encryption/decryption via Fernet.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog
from cryptography.fernet import Fernet, InvalidToken
from garminconnect import Garmin

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class GarminAuthError(Exception):
    """Raised when Garmin authentication fails."""


class GarminSyncError(Exception):
    """Raised when a Garmin sync operation fails."""


# ---------------------------------------------------------------------------
# Credential encryption helpers
# ---------------------------------------------------------------------------


def _derive_fernet_key(secret_key: str) -> bytes:
    """Derive a valid 32-byte Fernet key from an arbitrary secret string.

    Fernet requires a URL-safe base64-encoded 32-byte key.
    We use SHA256 to derive a deterministic 32-byte key from the secret.
    """
    raw = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_credentials(email: str, password: str, key: str) -> bytes:
    """Encrypt Garmin credentials as Fernet-encrypted JSON.

    Args:
        email: Garmin Connect email address.
        password: Garmin Connect password.
        key: Application SECRET_KEY used to derive Fernet key.

    Returns:
        Fernet-encrypted bytes containing JSON payload.
    """
    fernet = Fernet(_derive_fernet_key(key))
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    return fernet.encrypt(payload)


def decrypt_credentials(encrypted: bytes, key: str) -> tuple[str, str]:
    """Decrypt Fernet-encrypted Garmin credentials.

    Args:
        encrypted: Fernet-encrypted bytes from encrypt_credentials.
        key: Application SECRET_KEY used to derive Fernet key.

    Returns:
        Tuple of (email, password).

    Raises:
        GarminAuthError: If decryption fails (invalid key or corrupted data).
    """
    fernet = Fernet(_derive_fernet_key(key))
    try:
        decrypted = fernet.decrypt(encrypted)
    except InvalidToken as exc:
        raise GarminAuthError("Failed to decrypt credentials — invalid key or corrupted data") from exc

    data = json.loads(decrypted.decode("utf-8"))
    return data["email"], data["password"]


# ---------------------------------------------------------------------------
# Garmin service class
# ---------------------------------------------------------------------------


class GarminService:
    """Service for interacting with the Garmin Connect API.

    Uses the garminconnect library for authentication and data retrieval.
    All API interactions are encapsulated here so they can be easily mocked.
    """

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self._client: Garmin | None = None

    def login(self) -> None:
        """Authenticate with Garmin Connect.

        Uses garminconnect >= 0.3.1 mobile SSO flow (no garth dependency).
        See: https://github.com/matin/garth/discussions/222

        Raises:
            GarminAuthError: If authentication fails.
        """
        try:
            self._client = Garmin(self.email, self.password)
            self._client.login()
            logger.info("garmin_login_success", email=self.email)
        except Exception as exc:
            error_msg = str(exc)
            if "authentication" in error_msg.lower() or "login" in error_msg.lower():
                logger.warning("garmin_login_failed", email=self.email, error=error_msg)
                raise GarminAuthError(f"Garmin authentication failed: {exc}") from exc
            logger.error("garmin_connection_error", email=self.email, error=error_msg)
            raise GarminSyncError(f"Garmin connection error: {exc}") from exc

    def get_activities(self, since: datetime) -> list[dict[str, Any]]:
        """Fetch activities from Garmin Connect since a given datetime.

        Args:
            since: Only return activities after this datetime.

        Returns:
            List of activity dicts from Garmin API.

        Raises:
            GarminSyncError: If the API call fails.
        """
        if self._client is None:
            raise GarminSyncError("Not logged in — call login() first")

        try:
            # Garmin API returns activities in reverse chronological order.
            # Fetch a reasonable batch and filter by date.
            all_activities: list[dict[str, Any]] = self._client.get_activities(0, 100)

            filtered = []
            for act in all_activities:
                start_time = act.get("startTimeLocal") or act.get("startTimeGMT", "")
                if start_time:
                    try:
                        act_dt = datetime.fromisoformat(str(start_time))
                        if act_dt > since:
                            filtered.append(act)
                    except (ValueError, TypeError):
                        # If we can't parse the date, include it to be safe
                        filtered.append(act)

            logger.info(
                "garmin_activities_fetched",
                total=len(all_activities),
                filtered=len(filtered),
                since=since.isoformat(),
            )
            return filtered

        except (GarminConnectConnectionError, Exception) as exc:
            raise GarminSyncError(f"Failed to fetch activities: {exc}") from exc

    def download_fit(self, activity_id: str) -> bytes:
        """Download the FIT file for a specific Garmin activity.

        Args:
            activity_id: Garmin activity ID (string or numeric).

        Returns:
            Raw FIT file bytes.

        Raises:
            GarminSyncError: If the download fails.
        """
        if self._client is None:
            raise GarminSyncError("Not logged in — call login() first")

        try:
            fit_data = self._client.download_activity(
                activity_id, dl_fmt=self._client.ActivityDownloadFormat.ORIGINAL
            )
            logger.info(
                "garmin_fit_downloaded",
                activity_id=activity_id,
                size_bytes=len(fit_data) if fit_data else 0,
            )
            return bytes(fit_data) if fit_data else b""

        except Exception as exc:
            raise GarminSyncError(
                f"Failed to download FIT for activity {activity_id}: {exc}"
            ) from exc

    def get_health_data(self, target_date: date) -> dict[str, Decimal | None]:
        """Fetch health/wellness data for a specific date.

        Args:
            target_date: The date to retrieve health data for.

        Returns:
            Dict with keys: sleep_score, weight_kg, resting_hr, hrv_ms,
            body_battery, stress_avg. Values are Decimal or None.

        Raises:
            GarminSyncError: If the API call fails.
        """
        if self._client is None:
            raise GarminSyncError("Not logged in — call login() first")

        date_str = target_date.isoformat()
        result: dict[str, Decimal | None] = {
            "sleep_score": None,
            "weight_kg": None,
            "resting_hr": None,
            "hrv_ms": None,
            "body_battery": None,
            "stress_avg": None,
        }

        try:
            # Sleep data
            try:
                sleep_data = self._client.get_sleep_data(date_str)
                if sleep_data and isinstance(sleep_data, dict):
                    score = sleep_data.get("dailySleepDTO", {}).get("sleepScores", {}).get(
                        "overall", {}
                    ).get("value")
                    if score is not None:
                        result["sleep_score"] = Decimal(str(score))
            except Exception:
                logger.debug("garmin_sleep_data_unavailable", date=date_str)

            # Weight
            try:
                weight_data = self._client.get_body_composition(date_str)
                if weight_data and isinstance(weight_data, dict):
                    weight = weight_data.get("weight")
                    if weight is not None:
                        # Garmin returns weight in grams
                        result["weight_kg"] = Decimal(str(weight)) / Decimal("1000")
            except Exception:
                logger.debug("garmin_weight_data_unavailable", date=date_str)

            # Heart rate
            try:
                hr_data = self._client.get_heart_rates(date_str)
                if hr_data and isinstance(hr_data, dict):
                    resting = hr_data.get("restingHeartRate")
                    if resting is not None:
                        result["resting_hr"] = Decimal(str(resting))
            except Exception:
                logger.debug("garmin_hr_data_unavailable", date=date_str)

            # HRV
            try:
                hrv_data = self._client.get_hrv_data(date_str)
                if hrv_data and isinstance(hrv_data, dict):
                    summary = hrv_data.get("hrvSummary", {})
                    weekly_avg = summary.get("weeklyAvg")
                    if weekly_avg is not None:
                        result["hrv_ms"] = Decimal(str(weekly_avg))
            except Exception:
                logger.debug("garmin_hrv_data_unavailable", date=date_str)

            # Body battery
            try:
                bb_data = self._client.get_body_battery(date_str)
                if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
                    # Get the highest charged value of the day
                    max_bb = max(
                        (
                            item.get("charged", 0)
                            for item in bb_data
                            if isinstance(item, dict) and item.get("charged") is not None
                        ),
                        default=None,
                    )
                    if max_bb is not None:
                        result["body_battery"] = Decimal(str(max_bb))
            except Exception:
                logger.debug("garmin_body_battery_unavailable", date=date_str)

            # Stress
            try:
                stress_data = self._client.get_stress_data(date_str)
                if stress_data and isinstance(stress_data, dict):
                    avg_stress = stress_data.get("overallStressLevel")
                    if avg_stress is not None:
                        result["stress_avg"] = Decimal(str(avg_stress))
            except Exception:
                logger.debug("garmin_stress_data_unavailable", date=date_str)

            logger.info("garmin_health_data_fetched", date=date_str, metrics=result)
            return result

        except Exception as exc:
            raise GarminSyncError(f"Failed to fetch health data for {date_str}: {exc}") from exc
