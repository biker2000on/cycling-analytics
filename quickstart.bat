@echo off
REM Cycling Analytics - Development Quickstart Script (Windows)
REM Starts the development environment and provides helpful instructions

echo ===============================================================
echo   Cycling Analytics - Development Environment Setup
echo ===============================================================
echo.

REM Check if podman is available
where podman >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Podman not found. Please install Podman first.
    echo        https://podman.io/getting-started/installation
    exit /b 1
)

echo OK: Podman found
podman --version
echo.

REM Check if .env.local exists, create from example if not
if not exist ".env.local" (
    echo Creating .env.local from .env.example...
    copy .env.example .env.local >nul
    echo OK: Created .env.local
    echo.
)

REM Start development containers
echo Starting development database and Redis...
echo.
podman compose -f docker-compose.dev.yml up -d

REM Wait for database to be ready
echo.
echo Waiting for database to be ready...
timeout /t 3 /nobreak >nul

REM Check if database is healthy
podman compose -f docker-compose.dev.yml ps | findstr "healthy" >nul
if %errorlevel% equ 0 (
    echo OK: Database is ready!
) else (
    echo WARNING: Database is starting, may take a few more seconds...
)

echo.
echo ===============================================================
echo   SUCCESS: Development environment is running!
echo ===============================================================
echo.
echo Services:
echo   * PostgreSQL (TimescaleDB): localhost:5433
echo   * Redis: localhost:6379
echo.
echo Connection URLs:
echo   DATABASE_URL=postgresql+asyncpg://cycling_user:cycling_pass@localhost:5433/cycling_analytics
echo   REDIS_URL=redis://localhost:6379/0
echo.
echo Next steps:
echo.
echo   1. Run database migrations:
echo      cd backend ^&^& uv run alembic upgrade head
echo.
echo   2. Start the FastAPI development server:
echo      cd backend ^&^& uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo   3. In another terminal, start the Celery worker:
echo      cd backend ^&^& uv run celery -A app.workers.celery_app worker -Q high_priority,low_priority -c 4 --loglevel=info
echo.
echo   4. Visit the API documentation:
echo      http://localhost:8000/docs
echo.
echo ===============================================================
echo.
echo Useful commands:
echo   * View logs: podman compose -f docker-compose.dev.yml logs -f
echo   * Stop services: podman compose -f docker-compose.dev.yml down
echo   * Database shell: podman exec -it cycling-analytics-db-dev psql -U cycling_user -d cycling_analytics
echo.
echo For more information, see DOCKER.md
echo.
