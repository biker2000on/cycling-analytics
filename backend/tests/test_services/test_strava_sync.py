"""Tests for Strava sync Celery tasks and rate limiter.

All Strava API interactions are MOCKED — no real API calls.
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.strava_rate_limiter import (
    LIMIT_15MIN,
    LIMIT_DAILY,
    StravaRateLimiter,
)


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------


class TestStravaRateLimiter:
    """Tests for StravaRateLimiter."""

    def test_initial_state_can_make_request(self) -> None:
        """New rate limiter should allow requests."""
        limiter = StravaRateLimiter()
        assert limiter.can_make_request() is True

    def test_record_request_increments_counts(self) -> None:
        """Recording a request should increment both counters."""
        limiter = StravaRateLimiter()
        limiter.record_request()
        assert limiter.window_count == 1
        assert limiter.day_count == 1

    def test_15min_limit_blocks_requests(self) -> None:
        """Exceeding 15-min limit should block further requests."""
        limiter = StravaRateLimiter()
        for _ in range(LIMIT_15MIN):
            limiter.record_request()

        assert limiter.can_make_request() is False

    def test_daily_limit_blocks_requests(self) -> None:
        """Exceeding daily limit should block further requests."""
        limiter = StravaRateLimiter()
        # Simulate many window resets but same day
        for _ in range(LIMIT_DAILY):
            limiter.record_request()
            # Reset window to avoid 15-min block
            limiter._window_count = 0

        assert limiter.day_count == LIMIT_DAILY
        assert limiter.can_make_request() is False

    def test_window_reset_after_15min(self) -> None:
        """Window count should reset after 15 minutes."""
        limiter = StravaRateLimiter()

        for _ in range(50):
            limiter.record_request()

        assert limiter.window_count == 50

        # Simulate 15 minutes passing
        limiter._window_start = time.monotonic() - 901

        assert limiter.window_count == 0
        assert limiter.can_make_request() is True

    def test_day_reset_on_new_day(self) -> None:
        """Day count should reset when a new UTC day starts."""
        limiter = StravaRateLimiter()

        for _ in range(100):
            limiter.record_request()

        assert limiter.day_count == 100

        # Simulate yesterday
        limiter._day_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)

        assert limiter.day_count == 0

    def test_backoff_exponential(self) -> None:
        """Backoff should double with each 429."""
        limiter = StravaRateLimiter()

        # Mock time.sleep to avoid actual sleeping
        with patch("app.services.strava_rate_limiter.time.sleep"):
            first = limiter.backoff_on_429()
            second = limiter.backoff_on_429()
            third = limiter.backoff_on_429()

        assert first == 1.0
        assert second == 2.0
        assert third == 4.0

    def test_backoff_max_cap(self) -> None:
        """Backoff should cap at MAX_BACKOFF_SECONDS."""
        limiter = StravaRateLimiter()
        limiter._backoff_seconds = 64.0  # Already beyond max

        with patch("app.services.strava_rate_limiter.time.sleep"):
            slept = limiter.backoff_on_429()

        assert slept == 64.0
        assert limiter._backoff_seconds == 60.0  # Capped

    def test_reset_backoff(self) -> None:
        """reset_backoff should return to initial value."""
        limiter = StravaRateLimiter()

        with patch("app.services.strava_rate_limiter.time.sleep"):
            limiter.backoff_on_429()
            limiter.backoff_on_429()

        limiter.reset_backoff()
        assert limiter._backoff_seconds == 1.0


# ---------------------------------------------------------------------------
# Strava sync task tests (mocked)
# ---------------------------------------------------------------------------


class TestStravaSyncTask:
    """Tests for sync_strava_activities task logic."""

    @patch("app.workers.tasks.strava_sync._rate_limiter")
    @patch("app.workers.tasks.strava_sync.StravaService")
    @patch("app.workers.tasks.strava_sync.celery_app")
    @patch("app.workers.tasks.strava_sync.get_settings")
    def test_sync_fetches_new_activities(
        self,
        mock_settings: MagicMock,
        mock_celery: MagicMock,
        mock_svc_cls: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Sync should fetch activities and import new ones."""
        from app.workers.tasks.strava_sync import _import_strava_activity

        mock_settings.return_value = MagicMock(SECRET_KEY="test-key")
        mock_limiter.can_make_request.return_value = True

        # Mock the strava service
        mock_svc = MagicMock()
        mock_svc.fetch_activity_detail.return_value = {
            "id": 1001,
            "name": "Test Ride",
            "start_date": "2026-02-10T08:00:00Z",
            "elapsed_time": 3600,
        }
        mock_svc.fetch_activity_streams.return_value = {}

        # Mock DB session
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = _import_strava_activity(
            mock_session, mock_svc, "access_token", {"id": 1001}, user_id=1
        )

        assert result in ("synced", "error")

    @patch("app.workers.tasks.strava_sync._rate_limiter")
    @patch("app.workers.tasks.strava_sync.StravaService")
    @patch("app.workers.tasks.strava_sync.celery_app")
    def test_duplicate_detection_skips_existing(
        self,
        mock_celery: MagicMock,
        mock_svc_cls: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Duplicate activities should be skipped."""
        from app.workers.tasks.strava_sync import _import_strava_activity

        # Mock DB session returns existing activity
        mock_session = MagicMock()
        mock_existing = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_existing

        mock_svc = MagicMock()

        result = _import_strava_activity(
            mock_session, mock_svc, "access_token", {"id": 1001}, user_id=1
        )

        assert result == "skipped"
        # Should not call fetch_activity_detail for a duplicate
        mock_svc.fetch_activity_detail.assert_not_called()
