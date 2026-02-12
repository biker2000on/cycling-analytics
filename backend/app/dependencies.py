"""FastAPI dependency providers — database sessions, settings."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import AsyncSessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, rolling back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings_dep() -> Settings:
    """Dependency wrapper around cached settings for FastAPI Depends()."""
    return get_settings()
