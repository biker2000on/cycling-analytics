"""Health-check endpoint — database, Redis, and disk space."""

import shutil
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])
log = structlog.get_logger()


async def _ping_database() -> str:
    """Attempt to run a trivial query against the async database."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return "connected"
    except Exception as exc:
        log.warning("database_ping_failed", error=str(exc))
        return "disconnected"


async def _ping_redis() -> str:
    """Attempt to PING the Redis server."""
    try:
        from redis.asyncio import from_url

        settings = get_settings()
        client = from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.aclose()
        return "connected"
    except Exception as exc:
        log.warning("redis_ping_failed", error=str(exc))
        return "disconnected"


def _disk_free_gb() -> float:
    """Return free disk space (GB) on the FIT_STORAGE_PATH volume."""
    settings = get_settings()
    path = Path(settings.FIT_STORAGE_PATH)
    try:
        usage = shutil.disk_usage(path if path.exists() else Path("."))
        return round(usage.free / (1024**3), 1)
    except OSError:
        return 0.0


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return service health: database, Redis, and available disk space."""
    db_status = await _ping_database()
    redis_status = await _ping_redis()
    disk_gb = _disk_free_gb()

    status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"

    return {
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "disk_free_gb": disk_gb,
    }
