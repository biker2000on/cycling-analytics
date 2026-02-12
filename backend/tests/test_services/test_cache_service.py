"""Tests for the Redis cache service — Plan 2.5."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache_service import (
    CacheService,
    fitness_cache_key,
    metrics_cache_key,
    summary_cache_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_redis(connected: bool = True) -> AsyncMock:
    """Build a mock Redis client.

    If connected=False, ping() raises ConnectionError to simulate
    Redis being unavailable.
    """
    mock_client = AsyncMock()
    if not connected:
        mock_client.ping.side_effect = ConnectionError("Redis unavailable")
    else:
        mock_client.ping.return_value = True
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.close = AsyncMock()

    # scan_iter needs to be an async iterator
    async def _empty_scan_iter(**kwargs):  # type: ignore[no-untyped-def]
        return
        yield  # make it an async generator  # noqa: E501

    mock_client.scan_iter = _empty_scan_iter
    return mock_client


# ---------------------------------------------------------------------------
# Tests: get / set
# ---------------------------------------------------------------------------


class TestCacheGetSet:
    """Test basic get/set operations."""

    @pytest.mark.asyncio
    async def test_get_returns_cached_value(self) -> None:
        """get() returns a string when the key exists."""
        mock_client = _make_mock_redis()
        mock_client.get.return_value = '{"foo": "bar"}'

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get("test_key")

        assert result == '{"foo": "bar"}'
        mock_client.get.assert_awaited_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self) -> None:
        """get() returns None when the key does not exist."""
        mock_client = _make_mock_redis()
        mock_client.get.return_value = None

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get("missing_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_value_with_ttl(self) -> None:
        """set() stores a value with the specified TTL."""
        mock_client = _make_mock_redis()

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            await cache.set("my_key", "my_value", ttl_seconds=120)

        mock_client.set.assert_awaited_once_with("my_key", "my_value", ex=120)

    @pytest.mark.asyncio
    async def test_set_default_ttl_is_300(self) -> None:
        """set() uses 300s TTL by default."""
        mock_client = _make_mock_redis()

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            await cache.set("key", "val")

        mock_client.set.assert_awaited_once_with("key", "val", ex=300)


# ---------------------------------------------------------------------------
# Tests: delete_pattern
# ---------------------------------------------------------------------------


class TestCacheDeletePattern:
    """Test pattern-based key deletion."""

    @pytest.mark.asyncio
    async def test_delete_pattern_deletes_matching_keys(self) -> None:
        """delete_pattern() deletes all keys matching a glob pattern."""
        mock_client = _make_mock_redis()

        # Simulate scan_iter returning matching keys
        async def _scan_iter(**kwargs):  # type: ignore[no-untyped-def]
            for key in ["fitness:1:manual:2025-01-01:2025-03-01", "fitness:1:manual:2025-02-01:2025-04-01"]:
                yield key

        mock_client.scan_iter = _scan_iter

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            deleted = await cache.delete_pattern("fitness:1:*")

        assert deleted == 2
        assert mock_client.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_pattern_returns_zero_when_no_matches(self) -> None:
        """delete_pattern() returns 0 when no keys match."""
        mock_client = _make_mock_redis()

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            deleted = await cache.delete_pattern("nonexistent:*")

        assert deleted == 0


# ---------------------------------------------------------------------------
# Tests: invalidate_user
# ---------------------------------------------------------------------------


class TestCacheInvalidateUser:
    """Test user-level cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_user_clears_all_user_keys(self) -> None:
        """invalidate_user() calls delete_pattern for fitness, metrics, summary."""
        mock_client = _make_mock_redis()

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            # Patch delete_pattern to track calls
            with patch.object(cache, "delete_pattern", new_callable=AsyncMock) as mock_dp:
                mock_dp.return_value = 0
                await cache.invalidate_user(42)

            assert mock_dp.await_count == 3
            patterns = [call.args[0] for call in mock_dp.await_args_list]
            assert "fitness:42:*" in patterns
            assert "metrics:*" in patterns
            assert "summary:42:*" in patterns


# ---------------------------------------------------------------------------
# Tests: graceful degradation
# ---------------------------------------------------------------------------


class TestCacheGracefulDegradation:
    """Test that cache operations degrade gracefully when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_redis_unavailable(self) -> None:
        """get() returns None instead of crashing when Redis is down."""
        mock_client = _make_mock_redis(connected=False)

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get("any_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_crash_when_redis_unavailable(self) -> None:
        """set() silently does nothing when Redis is down."""
        mock_client = _make_mock_redis(connected=False)

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            # Should not raise
            await cache.set("key", "value", ttl_seconds=60)

    @pytest.mark.asyncio
    async def test_delete_pattern_returns_zero_when_redis_unavailable(self) -> None:
        """delete_pattern() returns 0 when Redis is down."""
        mock_client = _make_mock_redis(connected=False)

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            deleted = await cache.delete_pattern("some:*")

        assert deleted == 0

    @pytest.mark.asyncio
    async def test_get_json_returns_none_when_redis_unavailable(self) -> None:
        """get_json() returns None when Redis is down."""
        mock_client = _make_mock_redis(connected=False)

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get_json("any_key")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: JSON helpers
# ---------------------------------------------------------------------------


class TestCacheJsonHelpers:
    """Test JSON serialization/deserialization helpers."""

    @pytest.mark.asyncio
    async def test_get_json_deserializes_cached_value(self) -> None:
        """get_json() returns parsed JSON dict."""
        mock_client = _make_mock_redis()
        mock_client.get.return_value = json.dumps({"total_tss": "123.45", "ride_count": 5})

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get_json("summary:1:2025-01-01:2025-01-31")

        assert result is not None
        assert result["ride_count"] == 5

    @pytest.mark.asyncio
    async def test_set_json_serializes_and_stores(self) -> None:
        """set_json() serializes the value and calls set()."""
        mock_client = _make_mock_redis()

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            await cache.set_json("test_key", {"a": 1, "b": "two"}, ttl_seconds=60)

        # Verify the stored value is valid JSON
        stored = mock_client.set.call_args[0][1]
        parsed = json.loads(stored)
        assert parsed == {"a": 1, "b": "two"}

    @pytest.mark.asyncio
    async def test_get_json_handles_invalid_json(self) -> None:
        """get_json() returns None for invalid JSON instead of crashing."""
        mock_client = _make_mock_redis()
        mock_client.get.return_value = "not valid json{{"

        with patch("app.services.cache_service.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_client
            cache = CacheService("redis://localhost:6379/0", db=2)

            result = await cache.get_json("bad_key")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: cache key builders
# ---------------------------------------------------------------------------


class TestCacheKeyBuilders:
    """Test the cache key builder functions."""

    def test_fitness_cache_key(self) -> None:
        key = fitness_cache_key(1, "manual", "2025-01-01", "2025-03-31")
        assert key == "fitness:1:manual:2025-01-01:2025-03-31"

    def test_metrics_cache_key(self) -> None:
        key = metrics_cache_key(42, "auto")
        assert key == "metrics:42:auto"

    def test_summary_cache_key(self) -> None:
        key = summary_cache_key(1, "2025-01-01", "2025-01-31")
        assert key == "summary:1:2025-01-01:2025-01-31"
