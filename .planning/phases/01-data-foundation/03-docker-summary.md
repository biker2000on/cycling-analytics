# Plan 1.3: Docker Compose Infrastructure - Implementation Summary

**Date**: 2026-02-10
**Status**: ✅ Completed

## Overview

Implemented complete Docker Compose infrastructure for three deployment scenarios:
1. **Development** - DB + Redis in containers, Python runs locally
2. **Production** - External NAS database, all services in containers
3. **Standalone** - Complete stack including database

## Files Created

### Docker Compose Files

#### 1. `docker-compose.dev.yml`
- **Purpose**: Local development with fast iteration
- **Services**: PostgreSQL/TimescaleDB (port 5433), Redis (port 6379)
- **Key Features**:
  - Uses port 5433 to avoid conflict with existing fitnotes-db (port 5432)
  - Named volumes: `cycling_analytics_pgdata_dev`, `cycling_analytics_redis_dev`
  - Health checks for both services
  - PostGIS and TimescaleDB extensions enabled

#### 2. `docker-compose.yml`
- **Purpose**: Production with external NAS database
- **Services**: api, worker, redis, nginx
- **Key Features**:
  - Database connection via environment variables (DB_HOST, DB_PORT, etc.)
  - FIT file storage volume
  - Health checks on all services
  - Celery worker with high/low priority queues

#### 3. `docker-compose.full.yml`
- **Purpose**: Standalone deployment with included database
- **Services**: db, api, worker, redis, nginx
- **Key Features**:
  - Complete self-contained stack
  - Database runs on standard port 5432 (internal)
  - Same configuration as production, plus database service

### Backend

#### 4. `backend/Dockerfile`
- **Multi-stage build**:
  - Stage 1: Builder with uv for fast dependency installation
  - Stage 2: Slim runtime image with curl for health checks
- **Optimizations**:
  - Uses frozen lockfile (`uv sync --frozen --no-dev`)
  - No dev dependencies in production
  - Minimal layers
- **Default command**: uvicorn FastAPI server on port 8000
- **Override**: Can run Celery worker instead

#### 5. `backend/.dockerignore`
- Excludes: `__pycache__`, `.venv`, `.pytest_cache`, test files
- Includes: Source code, migrations, config files
- Reduces build context size

### Nginx

#### 6. `nginx/Dockerfile`
- Based on `nginx:alpine` for minimal size
- Includes placeholder HTML page for frontend
- Custom nginx configuration

#### 7. `nginx/nginx.conf`
- **Reverse proxy**:
  - `/api/*` → api:8000 (FastAPI backend)
  - `/docs`, `/redoc`, `/openapi.json` → API documentation
  - `/health` → Health check endpoint
  - `/` → Frontend placeholder (future React app)
- **Configuration**:
  - 60MB max body size (FIT file uploads)
  - Gzip compression
  - WebSocket support (future use)
  - Proper proxy headers

### Configuration

#### 8. `.env.example` (updated)
Added production/deployment variables:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`
- `APP_PORT` (default: 8000)
- Comments explaining three deployment modes
- Retained existing dev defaults

#### 9. `.gitignore` (updated)
Added backup exclusions:
- `backups/`
- `*.tar.gz`
- `*.sql.gz`

### Documentation

#### 10. `DOCKER.md`
Comprehensive deployment guide covering:
- Overview of three deployment scenarios
- Step-by-step setup instructions for each mode
- Common commands and operations
- Data persistence and backup strategies
- Troubleshooting guide
- Health check monitoring
- Production checklist

### Tooling

#### 11. `Makefile`
Convenient shortcuts for common operations:
- `make dev` - Start dev environment
- `make prod` - Start production stack
- `make full` - Start standalone stack
- `make migrate` - Run database migrations
- `make shell-db` - Open PostgreSQL shell
- `make ps` - Show all container status
- `make clean` - Clean up (with warning)
- `make backup` - Backup database volume

#### 12. `quickstart.sh`
Interactive setup script:
- Checks for Podman installation
- Creates `.env.local` from example if needed
- Starts dev containers
- Waits for database health check
- Provides next steps and helpful commands

## Key Design Decisions

### Port Configuration
- **Dev**: 5433:5432 (external:internal) - Avoids conflict with fitnotes-db
- **Prod/Full**: Standard 5432 port (or configurable via APP_PORT)

### Database Strategy
- **Dev**: Container with local volume (fast iteration)
- **Prod**: External NAS (shared, persistent)
- **Full**: Container with named volume (portable)

### Build Strategy
- Multi-stage Docker build for minimal image size
- uv for fast, reproducible dependency installation
- Frozen lockfile ensures consistency
- Separate builder stage keeps runtime image clean

### Volume Management
- Named volumes prevent accidental data loss
- Separate volumes for dev/prod avoid conflicts
- FIT file storage isolated for easy backup/migration

### Service Dependencies
- Health checks ensure proper startup order
- `depends_on` with `condition: service_healthy`
- API waits for Redis (and DB in full mode)
- Worker waits for Redis (and DB in full mode)
- Nginx waits for API

### Network Security
- Services communicate via internal Docker network
- Only nginx exposed on port 80 (production)
- API exposed on 8000 for development
- Database only exposed in dev/full modes

## Verification

All compose files validated successfully:

```bash
# Development
podman compose -f docker-compose.dev.yml config ✓

# Production
podman compose -f docker-compose.yml config ✓

# Standalone
podman compose -f docker-compose.full.yml config ✓
```

Expected warnings:
- Missing environment variables (normal without .env file)
- Version field obsolete (Compose v2 compatibility)

## Usage Examples

### Development Workflow
```bash
# Start DB + Redis
podman compose -f docker-compose.dev.yml up -d

# Run locally
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Production Deployment
```bash
# Configure .env with NAS database details
nano .env

# Deploy
podman compose up -d --build
podman compose exec api alembic upgrade head
```

### Standalone Testing
```bash
# Quick all-in-one deployment
podman compose -f docker-compose.full.yml up -d --build
podman compose -f docker-compose.full.yml exec api alembic upgrade head
```

## Next Steps

1. Test actual container startup (requires backend code)
2. Verify Alembic migrations work in containers
3. Test FIT file upload/storage
4. Configure SSL/TLS in nginx for production
5. Set up monitoring and log aggregation
6. Document backup/restore procedures
7. Create CI/CD pipeline for automated deployment

## Integration with Other Plans

- **Plan 1.1** (DB Models): Alembic migrations will run via `make migrate`
- **Plan 1.2** (API Skeleton): FastAPI app runs in `api` service
- **Future Plans**: Frontend will be served by nginx at `/`

## Notes

- Port 5433 specifically chosen due to existing fitnotes-db on 5432
- All services have restart policies (`unless-stopped`)
- Health checks ensure reliable deployments
- Makefile provides consistent commands across environments
- Documentation covers both Podman and Docker usage
