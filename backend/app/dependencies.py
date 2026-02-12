"""FastAPI dependency providers — database sessions, settings, auth."""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import jwt
import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import AsyncSessionLocal
from app.models.user import User

logger = structlog.get_logger(__name__)

# Seed user stub for DEBUG fallback (avoids DB query for backward compat)
_SEED_USER = SimpleNamespace(
    id=1,
    email="rider@localhost",
    display_name="Default Rider",
    weight_kg=None,
    date_of_birth=None,
    timezone="UTC",
)


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


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT Bearer token, return the authenticated User.

    Raises 401 if no token, invalid token, or user not found.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Strip "Bearer " prefix

    try:
        from app.security import decode_token

        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_or_default(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return authenticated user, or fallback to seed user (id=1) when DEBUG=True.

    This provides backward compatibility for Phases 1-4 tests that don't use auth.
    In production (DEBUG=False), authentication is always required.

    The DEBUG fallback uses a cached stub object (no DB query) to maintain
    backward compatibility with existing tests that mock only get_db.
    """
    settings = get_settings()

    if authorization is not None and authorization.startswith("Bearer "):
        # Token provided -- always validate it regardless of DEBUG mode
        return await get_current_user(authorization=authorization, db=db)

    if settings.DEBUG:
        # No token and DEBUG mode -- return seed user stub (no DB hit)
        return _SEED_USER  # type: ignore[return-value]

    # Production mode without token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
