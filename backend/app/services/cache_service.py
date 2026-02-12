"""Redis cache wrapper with graceful degradation.

Provides async get/set/delete operations backed by Redis db2.
If Redis is unavailable, operations silently return None / 0
so the application continues to function without caching.
"""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)


class CacheService:
    """Async Redis cache wrapper with graceful degradation."""

    def __init__(self, redis_url: str, db: int = 2) -> None:
        # Parse the base URL and override the db number
        self._redis_url = redis_url
        self._db = db
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis | None:
        """Lazily create and return the Redis client.

        Returns None if connection fails (graceful degradation).
        """
        if self._client is not None:
            return self._client
        try:
            self._client = aioredis.from_url(
                self._redis_url,
                db=self._db,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            # Verify connectivity
            await self._client.ping()
            return self._client
        except Exception:
            logger.warning("redis_unavailable", url=self._redis_url, db=self._db)
            self._client = None
            return None

    async def get(self, key: str) -> str | None:
        """Get a cached value by key.

        Returns None if the key does not exist or Redis is unavailable.
        """
        try:
            client = await self._get_client()
            if client is None:
                return None
            value = await client.get(key)
            return value  # type: ignore[return-value]
        except Exception:
            logger.warning("cache_get_failed", key=key)
            return None

    async def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        """Set a cached value with a TTL (default 5 minutes).

        Silently does nothing if Redis is unavailable.
        """
        try:
            client = await self._get_client()
            if client is None:
                return
            await client.set(key, value, ex=ttl_seconds)
        except Exception:
            logger.warning("cache_set_failed", key=key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching the given glob pattern.

        Returns the number of keys deleted, or 0 if Redis is unavailable.
        """
        try:
            client = await self._get_client()
            if client is None:
                return 0
            deleted = 0
            async for key in client.scan_iter(match=pattern, count=100):
                await client.delete(key)
                deleted += 1
            return deleted
        except Exception:
            logger.warning("cache_delete_pattern_failed", pattern=pattern)
            return 0

    async def invalidate_user(self, user_id: int) -> None:
        """Delete all cache keys for a specific user.

        Clears fitness:*, metrics:*, and summary:* keys for the user.
        """
        patterns = [
            f"fitness:{user_id}:*",
            f"metrics:*",  # metrics are keyed by activity_id, scan all
            f"summary:{user_id}:*",
        ]
        for pattern in patterns:
            await self.delete_pattern(pattern)

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Convenience: JSON serialization helpers
    # ------------------------------------------------------------------

    async def get_json(self, key: str) -> Any | None:
        """Get and deserialize a JSON-cached value."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("cache_json_decode_failed", key=key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Serialize a value to JSON and cache it."""
        try:
            raw = json.dumps(value, default=str)
        except (TypeError, ValueError):
            logger.warning("cache_json_encode_failed", key=key)
            return
        await self.set(key, raw, ttl_seconds)


# ---------------------------------------------------------------------------
# Cache key builders
# ---------------------------------------------------------------------------


def fitness_cache_key(
    user_id: int,
    threshold_method: str,
    start_date: str,
    end_date: str,
) -> str:
    """Build cache key for fitness time series."""
    return f"fitness:{user_id}:{threshold_method}:{start_date}:{end_date}"


def metrics_cache_key(activity_id: int, threshold_method: str) -> str:
    """Build cache key for per-activity metrics."""
    return f"metrics:{activity_id}:{threshold_method}"


def summary_cache_key(user_id: int, start_date: str, end_date: str) -> str:
    """Build cache key for period summary."""
    return f"summary:{user_id}:{start_date}:{end_date}"
