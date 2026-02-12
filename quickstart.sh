#!/usr/bin/env bash
# Cycling Analytics - Development Quickstart Script
# Starts the development environment and provides helpful instructions

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  Cycling Analytics - Development Environment Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if podman is available
if ! command -v podman &> /dev/null; then
    echo "❌ Podman not found. Please install Podman first."
    echo "   https://podman.io/getting-started/installation"
    exit 1
fi

echo "✓ Podman found: $(podman --version)"
echo ""

# Check if .env.local exists, create from example if not
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local from .env.example..."
    cp .env.example .env.local
    echo "✓ Created .env.local"
    echo ""
fi

# Start development containers
echo "🚀 Starting development database and Redis..."
echo ""
podman compose -f docker-compose.dev.yml up -d

# Wait for database to be healthy
echo ""
echo "⏳ Waiting for database to be ready..."
sleep 3

# Check if database is healthy
if podman compose -f docker-compose.dev.yml ps | grep -q "healthy"; then
    echo "✓ Database is ready!"
else
    echo "⚠️  Database is starting, may take a few more seconds..."
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Development environment is running!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Services:"
echo "  • PostgreSQL (TimescaleDB): localhost:5433"
echo "  • Redis: localhost:6379"
echo ""
echo "Connection URLs:"
echo "  DATABASE_URL=postgresql+asyncpg://cycling_user:cycling_pass@localhost:5433/cycling_analytics"
echo "  REDIS_URL=redis://localhost:6379/0"
echo ""
echo "Next steps:"
echo ""
echo "  1️⃣  Run database migrations:"
echo "     cd backend && uv run alembic upgrade head"
echo ""
echo "  2️⃣  Start the FastAPI development server:"
echo "     cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  3️⃣  In another terminal, start the Celery worker:"
echo "     cd backend && uv run celery -A app.workers.celery_app worker -Q high_priority,low_priority -c 4 --loglevel=info"
echo ""
echo "  4️⃣  Visit the API documentation:"
echo "     http://localhost:8000/docs"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Useful commands:"
echo "  • View logs: podman compose -f docker-compose.dev.yml logs -f"
echo "  • Stop services: podman compose -f docker-compose.dev.yml down"
echo "  • Database shell: podman exec -it cycling-analytics-db-dev psql -U cycling_user -d cycling_analytics"
echo ""
echo "For more information, see DOCKER.md"
echo ""
