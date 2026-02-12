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
    FRONTEND_URL: str = "http://localhost:5173"

    # Strava OAuth2
    STRAVA_CLIENT_ID: str = ""
    STRAVA_CLIENT_SECRET: str = ""
    STRAVA_REDIRECT_URI: str = "http://localhost:8000/integrations/strava/callback"
    STRAVA_VERIFY_TOKEN: str = "cycling-analytics-verify"

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (reads env vars once)."""
    return Settings()
