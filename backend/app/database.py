"""Central database module — engines, session factories, and declarative base.

Async engine (asyncpg)  -> FastAPI request handlers
Sync engine  (psycopg2) -> Celery workers + Alembic migrations
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ---------------------------------------------------------------------------
# Async engine + session (FastAPI)
# ---------------------------------------------------------------------------

_settings = get_settings()

async_engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Sync engine + session (Celery / Alembic)
# ---------------------------------------------------------------------------

sync_engine = create_engine(
    _settings.SYNC_DATABASE_URL,
    echo=_settings.DEBUG,
    pool_pre_ping=True,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)

__all__ = [
    "Base",
    "async_engine",
    "AsyncSessionLocal",
    "sync_engine",
    "SyncSessionLocal",
]
