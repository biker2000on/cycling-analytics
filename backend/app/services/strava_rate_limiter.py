"""Strava API rate limiter.

Tracks requests per 15-minute window (max 200) and per day (max 2000).
Provides backoff logic for 429 responses.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger(__name__)

# Strava rate limits
LIMIT_15MIN = 200
LIMIT_DAILY = 2000

# Backoff settings
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0
BACKOFF_MULTIPLIER = 2.0


class StravaRateLimiter:
    """Track Strava API request counts and enforce rate limits.

    Thread-safe for single-worker Celery usage. For multi-worker,
    consider using Redis-backed counters instead.
    """

    def __init__(self) -> None:
        self._window_start: float = time.monotonic()
        self._window_count: int = 0
        self._day_start: datetime = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._day_count: int = 0
        self._backoff_seconds: float = INITIAL_BACKOFF_SECONDS

    def _reset_window_if_needed(self) -> None:
        """Reset the 15-minute window counter if elapsed."""
        elapsed = time.monotonic() - self._window_start
        if elapsed >= 900:  # 15 minutes
            self._window_count = 0
            self._window_start = time.monotonic()

    def _reset_day_if_needed(self) -> None:
        """Reset the daily counter if a new UTC day has started."""
        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if today > self._day_start:
            self._day_count = 0
            self._day_start = today

    def can_make_request(self) -> bool:
        """Check whether a request can be made within rate limits.

        Returns:
            True if both 15-min and daily limits have headroom.
        """
        self._reset_window_if_needed()
        self._reset_day_if_needed()
        return self._window_count < LIMIT_15MIN and self._day_count < LIMIT_DAILY

    def record_request(self) -> None:
        """Record that a request was made. Call after each API request."""
        self._reset_window_if_needed()
        self._reset_day_if_needed()
        self._window_count += 1
        self._day_count += 1

    def wait_if_needed(self) -> None:
        """Sleep if approaching rate limits (>80% of 15-min window).

        Blocks the calling thread until the rate limit window resets
        or headroom is available.
        """
        self._reset_window_if_needed()
        self._reset_day_if_needed()

        if self._window_count >= int(LIMIT_15MIN * 0.8):
            elapsed = time.monotonic() - self._window_start
            wait_time = max(0, 900 - elapsed)
            if wait_time > 0:
                logger.warning(
                    "strava_rate_limit_approaching",
                    window_count=self._window_count,
                    wait_seconds=wait_time,
                )
                time.sleep(min(wait_time, MAX_BACKOFF_SECONDS))

    def backoff_on_429(self) -> float:
        """Apply exponential backoff after a 429 response.

        Returns:
            The number of seconds slept.
        """
        sleep_time = self._backoff_seconds
        logger.warning("strava_rate_limit_429_backoff", seconds=sleep_time)
        time.sleep(sleep_time)

        # Exponential increase for next 429
        self._backoff_seconds = min(
            self._backoff_seconds * BACKOFF_MULTIPLIER,
            MAX_BACKOFF_SECONDS,
        )
        return sleep_time

    def reset_backoff(self) -> None:
        """Reset backoff after a successful request."""
        self._backoff_seconds = INITIAL_BACKOFF_SECONDS

    @property
    def window_count(self) -> int:
        """Current count in the 15-minute window."""
        self._reset_window_if_needed()
        return self._window_count

    @property
    def day_count(self) -> int:
        """Current count for the day."""
        self._reset_day_if_needed()
        return self._day_count
