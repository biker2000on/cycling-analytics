# Cycling Analytics - Docker Compose Management
# Podman-compatible (also works with Docker)

.PHONY: help dev prod full stop clean logs ps shell-db shell-api test migrate build

# Default target
help:
	@echo "Cycling Analytics - Docker Management"
	@echo ""
	@echo "Development (DB + Redis only):"
	@echo "  make dev           Start dev database + Redis (port 5433)"
	@echo "  make dev-stop      Stop dev services"
	@echo "  make dev-logs      View dev logs"
	@echo ""
	@echo "Production (external DB):"
	@echo "  make prod          Start production stack (requires .env)"
	@echo "  make prod-stop     Stop production stack"
	@echo "  make prod-logs     View production logs"
	@echo "  make prod-build    Rebuild production images"
	@echo ""
	@echo "Standalone (all-in-one):"
	@echo "  make full          Start standalone stack with DB"
	@echo "  make full-stop     Stop standalone stack"
	@echo "  make full-logs     View standalone logs"
	@echo "  make full-build    Rebuild standalone images"
	@echo ""
	@echo "Database operations:"
	@echo "  make migrate       Run database migrations"
	@echo "  make shell-db      Open PostgreSQL shell"
	@echo "  make shell-api     Open Python shell in API container"
	@echo ""
	@echo "Common:"
	@echo "  make ps            Show container status"
	@echo "  make logs          Tail all logs"
	@echo "  make clean         Remove all containers and volumes"

# Development compose (DB + Redis only)
dev:
	podman compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "✓ Dev database running on port 5433"
	@echo "  DATABASE_URL=postgresql+asyncpg://cycling_user:cycling_pass@localhost:5433/cycling_analytics"
	@echo ""
	@echo "Run locally with:"
	@echo "  cd backend && uv run uvicorn app.main:app --reload"

dev-stop:
	podman compose -f docker-compose.dev.yml down

dev-logs:
	podman compose -f docker-compose.dev.yml logs -f

# Production compose (external DB)
prod:
	podman compose up -d
	@echo ""
	@echo "✓ Production stack running"
	@echo "  API: http://localhost (nginx)"
	@echo "  Docs: http://localhost/docs"

prod-stop:
	podman compose down

prod-logs:
	podman compose logs -f

prod-build:
	podman compose build --no-cache
	podman compose up -d

# Standalone compose (all-in-one)
full:
	podman compose -f docker-compose.full.yml up -d
	@echo ""
	@echo "✓ Standalone stack running"
	@echo "  API: http://localhost"
	@echo "  Database: localhost:5432"

full-stop:
	podman compose -f docker-compose.full.yml down

full-logs:
	podman compose -f docker-compose.full.yml logs -f

full-build:
	podman compose -f docker-compose.full.yml build --no-cache
	podman compose -f docker-compose.full.yml up -d

# Database operations
migrate:
	podman compose exec api alembic upgrade head

migrate-dev:
	cd backend && uv run alembic upgrade head

shell-db:
	podman compose exec db psql -U cycling_user -d cycling_analytics

shell-db-dev:
	podman exec -it cycling-analytics-db-dev psql -U cycling_user -d cycling_analytics

shell-api:
	podman compose exec api python

shell-worker:
	podman compose exec worker python

# Common operations
ps:
	@echo "=== Development ==="
	@podman compose -f docker-compose.dev.yml ps || true
	@echo ""
	@echo "=== Production ==="
	@podman compose ps || true
	@echo ""
	@echo "=== Standalone ==="
	@podman compose -f docker-compose.full.yml ps || true

logs:
	podman compose logs -f

# Clean up (WARNING: removes volumes)
clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		podman compose -f docker-compose.dev.yml down -v; \
		podman compose down -v; \
		podman compose -f docker-compose.full.yml down -v; \
		echo "✓ Cleaned up all containers and volumes"; \
	fi

# Backup database
backup:
	@mkdir -p backups
	podman run --rm \
		-v cycling_analytics_pgdata:/data \
		-v $(PWD)/backups:/backup \
		alpine tar czf /backup/pgdata-$$(date +%Y%m%d-%H%M%S).tar.gz /data
	@echo "✓ Backup saved to backups/"
