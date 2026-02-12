"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from .env.local (dev) or environment variables (prod)."""

    # Database — async driver for FastAPI, sync driver for Celery workers
    DATABASE_URL: str = (
        "postgresql+asyncpg://cycling_user:cycling_pass@localhost:5433/cycling_analytics"
    )
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg2://cycling_user:cycling_pass@localhost:5433/cycling_analytics"
    )

    # Redis — broker=db0, results=db1, cache=db2
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 2

    # File storage
    FIT_STORAGE_PATH: str = "./data/fit_files"

    # App
    APP_NAME: str = "Cycling Analytics"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (reads env vars once)."""
    return Settings()
