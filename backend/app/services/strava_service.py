"""Strava integration service.

Handles OAuth2 flow, activity fetching, stream retrieval,
and conversion to internal data format. Uses httpx for HTTP.
Token encryption/decryption via Fernet (same pattern as Garmin service).
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Strava API constants
# ---------------------------------------------------------------------------

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Activity list page size (max 200 per Strava docs)
PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class StravaAuthError(Exception):
    """Raised when Strava authentication or token exchange fails."""


class StravaSyncError(Exception):
    """Raised when a Strava sync operation fails."""


# ---------------------------------------------------------------------------
# Token encryption helpers (mirrors Garmin pattern)
# ---------------------------------------------------------------------------


def _derive_fernet_key(secret_key: str) -> bytes:
    """Derive a valid 32-byte Fernet key from an arbitrary secret string."""
    raw = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_token(token: str, key: str) -> bytes:
    """Encrypt a single token string with Fernet.

    Args:
        token: Plain-text token value.
        key: Application SECRET_KEY for key derivation.

    Returns:
        Fernet-encrypted bytes.
    """
    fernet = Fernet(_derive_fernet_key(key))
    return fernet.encrypt(token.encode("utf-8"))


def decrypt_token(encrypted: bytes, key: str) -> str:
    """Decrypt a Fernet-encrypted token.

    Args:
        encrypted: Fernet-encrypted bytes from encrypt_token.
        key: Application SECRET_KEY for key derivation.

    Returns:
        Plain-text token string.

    Raises:
        StravaAuthError: If decryption fails.
    """
    fernet = Fernet(_derive_fernet_key(key))
    try:
        return fernet.decrypt(encrypted).decode("utf-8")
    except InvalidToken as exc:
        raise StravaAuthError(
            "Failed to decrypt Strava token — invalid key or corrupted data"
        ) from exc


# ---------------------------------------------------------------------------
# Strava service class
# ---------------------------------------------------------------------------


class StravaService:
    """Service for interacting with the Strava API.

    Uses httpx for all HTTP requests. All external calls are encapsulated
    here so they can be easily mocked in tests.
    """

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    # --- OAuth2 flow ---

    def build_auth_url(self, redirect_uri: str) -> str:
        """Build the Strava OAuth2 authorization URL.

        Args:
            redirect_uri: Where Strava should redirect after authorization.

        Returns:
            Full authorization URL string.
        """
        settings = get_settings()
        params = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all",
        }
        return f"{STRAVA_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an authorization code for access and refresh tokens.

        Args:
            code: Authorization code from Strava callback.
            redirect_uri: Must match the redirect_uri used in authorization.

        Returns:
            Dict with keys: access_token, refresh_token, expires_at, athlete.

        Raises:
            StravaAuthError: If the token exchange fails.
        """
        settings = get_settings()
        payload = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        }

        try:
            response = self._client.post(STRAVA_TOKEN_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("strava_code_exchanged", athlete_id=data.get("athlete", {}).get("id"))
            return data
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "strava_code_exchange_failed",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise StravaAuthError(
                f"Strava token exchange failed: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaAuthError(f"Strava connection error: {exc}") from exc

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token using the refresh token.

        Args:
            refresh_token: Valid Strava refresh token.

        Returns:
            Dict with keys: access_token, refresh_token, expires_at.

        Raises:
            StravaAuthError: If the refresh fails.
        """
        settings = get_settings()
        payload = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "client_secret": settings.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = self._client.post(STRAVA_TOKEN_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("strava_tokens_refreshed")
            return data
        except httpx.HTTPStatusError as exc:
            raise StravaAuthError(
                f"Strava token refresh failed: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaAuthError(f"Strava connection error: {exc}") from exc

    def get_athlete_info(self, access_token: str) -> dict[str, Any]:
        """Fetch authenticated athlete profile.

        Args:
            access_token: Valid Strava access token.

        Returns:
            Dict with athlete info (id, firstname, lastname, etc.).

        Raises:
            StravaAuthError: If the request fails.
        """
        try:
            response = self._client.get(
                f"{STRAVA_API_BASE}/athlete",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise StravaAuthError(
                f"Failed to fetch athlete info: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaAuthError(f"Strava connection error: {exc}") from exc

    # --- Activity fetching ---

    def fetch_activities_since(
        self,
        access_token: str,
        after_epoch: int,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch athlete activities since a given epoch timestamp.

        Args:
            access_token: Valid Strava access token.
            after_epoch: Unix epoch — only return activities after this time.
            page: Page number (1-indexed).

        Returns:
            List of activity summary dicts from Strava.

        Raises:
            StravaSyncError: If the request fails.
        """
        try:
            response = self._client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"after": after_epoch, "page": page, "per_page": PAGE_SIZE},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise StravaSyncError(
                f"Failed to fetch activities: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaSyncError(f"Strava connection error: {exc}") from exc

    def fetch_activity_detail(
        self,
        access_token: str,
        activity_id: int,
    ) -> dict[str, Any]:
        """Fetch full detail for a single Strava activity.

        Args:
            access_token: Valid Strava access token.
            activity_id: Strava activity ID.

        Returns:
            Full activity detail dict.

        Raises:
            StravaSyncError: If the request fails.
        """
        try:
            response = self._client.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise StravaSyncError(
                f"Failed to fetch activity {activity_id}: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaSyncError(f"Strava connection error: {exc}") from exc

    def fetch_activity_streams(
        self,
        access_token: str,
        activity_id: int,
    ) -> dict[str, Any]:
        """Fetch time-series streams for a Strava activity.

        Requests: time, distance, altitude, heartrate, cadence, watts, latlng.

        Args:
            access_token: Valid Strava access token.
            activity_id: Strava activity ID.

        Returns:
            Dict keyed by stream type, each with 'data' array.

        Raises:
            StravaSyncError: If the request fails.
        """
        stream_types = "time,distance,altitude,heartrate,cadence,watts,latlng"
        try:
            response = self._client.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"keys": stream_types, "key_by_type": "true"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # 404 means no streams available (e.g. manual activity)
            if exc.response.status_code == 404:
                logger.debug("strava_no_streams", activity_id=activity_id)
                return {}
            raise StravaSyncError(
                f"Failed to fetch streams for {activity_id}: {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise StravaSyncError(f"Strava connection error: {exc}") from exc

    # --- Data conversion ---

    @staticmethod
    def convert_strava_to_internal(
        strava_activity: dict[str, Any],
        streams: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Convert a Strava activity + streams to internal format.

        Args:
            strava_activity: Strava activity detail dict.
            streams: Strava streams dict (keyed by type).

        Returns:
            Tuple of (activity_data dict, list of stream record dicts).
            activity_data keys match Activity model fields.
            stream records match ActivityStream fields.
        """
        # Parse start date
        start_date_str = strava_activity.get("start_date", "")
        try:
            activity_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            activity_date = datetime.now(UTC)

        # Build activity data
        activity_data: dict[str, Any] = {
            "external_id": str(strava_activity.get("id", "")),
            "name": strava_activity.get("name", "Strava Activity"),
            "sport_type": strava_activity.get("sport_type") or strava_activity.get("type"),
            "activity_date": activity_date,
            "duration_seconds": int(strava_activity.get("elapsed_time", 0)) or None,
            "distance_meters": (
                Decimal(str(strava_activity["distance"]))
                if strava_activity.get("distance")
                else None
            ),
            "elevation_gain_meters": (
                Decimal(str(strava_activity["total_elevation_gain"]))
                if strava_activity.get("total_elevation_gain")
                else None
            ),
            "avg_power_watts": (
                Decimal(str(strava_activity["average_watts"]))
                if strava_activity.get("average_watts")
                else None
            ),
            "max_power_watts": (
                Decimal(str(strava_activity["max_watts"]))
                if strava_activity.get("max_watts")
                else None
            ),
            "avg_hr": (
                int(strava_activity["average_heartrate"])
                if strava_activity.get("average_heartrate")
                else None
            ),
            "max_hr": (
                int(strava_activity["max_heartrate"])
                if strava_activity.get("max_heartrate")
                else None
            ),
            "avg_cadence": (
                int(strava_activity["average_cadence"])
                if strava_activity.get("average_cadence")
                else None
            ),
            "calories": (
                int(strava_activity["calories"])
                if strava_activity.get("calories")
                else None
            ),
            "device_name": strava_activity.get("device_name"),
        }

        # Build stream records
        stream_records: list[dict[str, Any]] = []

        time_data = _get_stream_data(streams, "time")
        if not time_data:
            return activity_data, stream_records

        distance_data = _get_stream_data(streams, "distance")
        altitude_data = _get_stream_data(streams, "altitude")
        hr_data = _get_stream_data(streams, "heartrate")
        cadence_data = _get_stream_data(streams, "cadence")
        watts_data = _get_stream_data(streams, "watts")
        latlng_data = _get_stream_data(streams, "latlng")

        for i, elapsed in enumerate(time_data):
            ts = activity_date + timedelta(seconds=elapsed)

            record: dict[str, Any] = {
                "timestamp": ts,
                "elapsed_seconds": elapsed,
                "power_watts": _safe_index(watts_data, i),
                "heart_rate": _safe_index(hr_data, i),
                "cadence": _safe_index(cadence_data, i),
                "altitude_meters": (
                    Decimal(str(altitude_data[i]))
                    if altitude_data and i < len(altitude_data) and altitude_data[i] is not None
                    else None
                ),
                "distance_meters": (
                    Decimal(str(distance_data[i]))
                    if distance_data and i < len(distance_data) and distance_data[i] is not None
                    else None
                ),
                "position": None,
            }

            # GPS from latlng stream: [[lat, lng], [lat, lng], ...]
            if latlng_data and i < len(latlng_data) and latlng_data[i] is not None:
                lat, lng = latlng_data[i]
                record["position"] = f"SRID=4326;POINT({lng} {lat})"

            stream_records.append(record)

        return activity_data, stream_records

    # --- Backfill ---

    def backfill_all_activities(
        self,
        access_token: str,
    ) -> list[dict[str, Any]]:
        """Fetch ALL athlete activities by paginating from page 1.

        Args:
            access_token: Valid Strava access token.

        Returns:
            List of all activity summary dicts.
        """
        all_activities: list[dict[str, Any]] = []
        page = 1

        while True:
            batch = self.fetch_activities_since(access_token, after_epoch=0, page=page)
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1

        logger.info("strava_backfill_fetched", total=len(all_activities))
        return all_activities


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_stream_data(streams: dict[str, Any], key: str) -> list[Any] | None:
    """Extract the 'data' array from a Strava stream dict."""
    stream = streams.get(key)
    if stream and isinstance(stream, dict):
        return stream.get("data")
    return None


def _safe_index(data: list[Any] | None, i: int) -> int | None:
    """Safely index into an optional list, returning None on miss."""
    if data is not None and i < len(data):
        return data[i]
    return None
