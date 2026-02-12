# Docker Deployment Guide

This project provides three Docker Compose configurations for different deployment scenarios.

## Overview

| File | Use Case | Database | Services |
|------|----------|----------|----------|
| `docker-compose.dev.yml` | Local development | Container (port 5433) | DB + Redis only |
| `docker-compose.yml` | Production | External NAS | API + Worker + Redis + Nginx |
| `docker-compose.full.yml` | Standalone | Container (port 5432) | All (including DB) |

## Prerequisites

- Podman 5.1.1+ or Docker 24.0+
- docker-compose / podman-compose

## 1. Development Setup (Recommended)

For local development with hot-reload and debugging.

### What runs where:
- **In containers**: PostgreSQL/TimescaleDB (port 5433), Redis (port 6379)
- **On host**: FastAPI, Celery worker (via `uv`)

### Setup:

```bash
# 1. Start database and Redis
podman compose -f docker-compose.dev.yml up -d

# 2. Copy environment template
cp .env.example .env.local

# 3. Ensure DATABASE_URL uses port 5433 (dev container)
# DATABASE_URL=postgresql+asyncpg://cycling_user:cycling_pass@localhost:5433/cycling_analytics
# SYNC_DATABASE_URL=postgresql+psycopg2://cycling_user:cycling_pass@localhost:5433/cycling_analytics

# 4. Run migrations
cd backend
uv run alembic upgrade head

# 5. Start FastAPI dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. In another terminal, start Celery worker
uv run celery -A app.workers.celery_app worker -Q high_priority,low_priority -c 4 --loglevel=info
```

### Why port 5433?
Port 5432 is already used by the `fitnotes-db` container, so the dev database uses 5433 to avoid conflicts.

### Verify:
```bash
# Check container status
podman compose -f docker-compose.dev.yml ps

# Check logs
podman compose -f docker-compose.dev.yml logs -f db
```

## 2. Production Deployment (External Database)

For production deployments where the database runs on a NAS or external server.

### What runs where:
- **On NAS**: PostgreSQL/TimescaleDB
- **In containers**: FastAPI, Celery worker, Redis, Nginx

### Setup:

```bash
# 1. Create .env file with database connection details
cat > .env << EOF
# Database on NAS
DB_HOST=nas.local
DB_PORT=5432
DB_USER=cycling_user
DB_PASS=your_secure_password
DB_NAME=cycling_analytics

# Application
APP_PORT=8000
SECRET_KEY=$(openssl rand -hex 32)
DEBUG=false
EOF

# 2. Build and start services
podman compose up -d --build

# 3. Run migrations (one-time)
podman compose exec api alembic upgrade head
```

### Access:
- Frontend: http://localhost
- API docs: http://localhost/docs
- API endpoints: http://localhost/api/*

### Database setup on NAS:
```sql
-- Run on NAS PostgreSQL server
CREATE USER cycling_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE cycling_analytics OWNER cycling_user;

-- Connect to cycling_analytics database
\c cycling_analytics

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE cycling_analytics TO cycling_user;
```

## 3. Standalone Deployment (All-in-One)

For testing or deployments without external database.

### What runs where:
- **In containers**: Everything (DB, API, Worker, Redis, Nginx)

### Setup:

```bash
# 1. Create minimal .env file
cat > .env << EOF
# Use defaults from docker-compose.full.yml
DB_USER=cycling_user
DB_PASS=cycling_pass
DB_NAME=cycling_analytics
SECRET_KEY=$(openssl rand -hex 32)
DEBUG=false
EOF

# 2. Build and start all services
podman compose -f docker-compose.full.yml up -d --build

# 3. Wait for database to be ready (check healthcheck)
podman compose -f docker-compose.full.yml ps

# 4. Run migrations
podman compose -f docker-compose.full.yml exec api alembic upgrade head
```

### Access:
Same as production deployment (http://localhost).

## Common Commands

### View logs:
```bash
# All services
podman compose logs -f

# Specific service
podman compose logs -f api
podman compose logs -f worker
```

### Restart services:
```bash
# All services
podman compose restart

# Specific service
podman compose restart api
```

### Stop and remove:
```bash
# Stop services
podman compose down

# Stop and remove volumes (WARNING: deletes data)
podman compose down -v
```

### Execute commands in containers:
```bash
# Database shell
podman compose exec db psql -U cycling_user -d cycling_analytics

# Redis CLI
podman compose exec redis redis-cli

# Python shell in API container
podman compose exec api python
```

### Rebuild after code changes:
```bash
# Rebuild and restart
podman compose up -d --build

# Force rebuild
podman compose build --no-cache
podman compose up -d
```

## Data Persistence

Named volumes ensure data survives container restarts:

### Development:
- `cycling_analytics_pgdata_dev` - Database files
- `cycling_analytics_redis_dev` - Redis persistence

### Production/Full:
- `cycling_analytics_pgdata` - Database files (full mode only)
- `cycling_analytics_fit_files` - Uploaded FIT files
- `cycling_analytics_redis` - Redis persistence

### Backup volumes:
```bash
# List volumes
podman volume ls

# Inspect volume
podman volume inspect cycling_analytics_pgdata

# Backup database volume
podman run --rm -v cycling_analytics_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata-backup-$(date +%Y%m%d).tar.gz /data
```

## Troubleshooting

### Port 5432 already in use (development):
The dev compose uses port 5433 specifically to avoid conflicts with `fitnotes-db`. Ensure your `.env.local` uses `localhost:5433`.

### Container won't start:
```bash
# Check logs
podman compose logs service_name

# Check container status
podman compose ps -a

# Force recreate
podman compose up -d --force-recreate service_name
```

### Database connection errors:
```bash
# Verify database is healthy
podman compose exec db pg_isready -U cycling_user -d cycling_analytics

# Check environment variables
podman compose exec api env | grep DATABASE_URL
```

### Permission errors:
```bash
# Fix volume permissions (if needed)
podman unshare chown -R 1000:1000 /path/to/volume
```

## Health Checks

All services have health checks defined:

- **Database**: `pg_isready` command
- **Redis**: `redis-cli ping`
- **API**: HTTP GET to `/health`

Check health status:
```bash
podman compose ps
```

Healthy services show `Up (healthy)` in status.

## Monitoring

### Resource usage:
```bash
# Container stats
podman stats

# Specific container
podman stats cycling-analytics-api
```

### Database statistics:
```sql
-- Connect to database
podman compose exec db psql -U cycling_user -d cycling_analytics

-- Check database size
SELECT pg_size_pretty(pg_database_size('cycling_analytics'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Production Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Set `DEBUG=false`
- [ ] Use strong database password
- [ ] Configure firewall rules
- [ ] Set up SSL/TLS (add to nginx config)
- [ ] Configure backup strategy for volumes
- [ ] Set up monitoring/alerting
- [ ] Review and adjust worker concurrency (`-c` flag)
- [ ] Configure log rotation
- [ ] Test migrations on staging environment first

## Next Steps

- Configure nginx SSL/TLS certificates
- Set up automated backups
- Add monitoring (Prometheus/Grafana)
- Implement log aggregation (ELK/Loki)
- Set up CI/CD pipeline
