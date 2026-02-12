# Cycling Analytics Platform

A comprehensive cycling analytics platform for processing, analyzing, and visualizing training data from FIT files.

## Features

- **FIT File Processing**: Parse and extract detailed metrics from Garmin FIT files
- **Advanced Analytics**: Power zones, heart rate analysis, training load metrics
- **Geospatial Analysis**: Route tracking, elevation profiling, segment analysis
- **Time-Series Data**: Efficient storage with TimescaleDB for performance over time
- **Async API**: High-performance FastAPI backend
- **Background Processing**: Celery task queue for heavy computations
- **RESTful API**: Well-documented OpenAPI/Swagger interface

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 17 + TimescaleDB + PostGIS
- **Task Queue**: Celery + Redis
- **Reverse Proxy**: Nginx
- **Containers**: Podman/Docker Compose
- **Dependency Management**: uv (ultra-fast Python package manager)

## Quick Start

### Prerequisites

- [Podman](https://podman.io) 5.1.1+ or Docker 24.0+
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- Python 3.13+

### Development Setup (Recommended)

The fastest way to get started for development:

#### Linux/macOS:
```bash
# 1. Clone the repository
git clone <repo-url>
cd cycling-analytics

# 2. Run quickstart script
chmod +x quickstart.sh
./quickstart.sh

# 3. Follow the on-screen instructions
```

#### Windows:
```cmd
# 1. Clone the repository
git clone <repo-url>
cd cycling-analytics

# 2. Run quickstart script
quickstart.bat

# 3. Follow the on-screen instructions
```

#### Manual Setup:

```bash
# 1. Start database and Redis containers
podman compose -f docker-compose.dev.yml up -d

# 2. Create environment file
cp .env.example .env.local

# 3. Install Python dependencies
cd backend
uv sync

# 4. Run database migrations
uv run alembic upgrade head

# 5. Start the API server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. In another terminal, start the Celery worker
cd backend
uv run celery -A app.workers.celery_app worker -Q high_priority,low_priority -c 4 --loglevel=info
```

### Access the Application

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Deployment

See [DOCKER.md](./DOCKER.md) for detailed deployment instructions covering:

- **Development**: Local development with hot-reload
- **Production**: External database on NAS
- **Standalone**: Complete containerized stack

### Quick Production Deploy

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 2. Deploy
podman compose up -d --build

# 3. Run migrations
podman compose exec api alembic upgrade head
```

## Project Structure

```
cycling-analytics/
├── backend/                    # Python FastAPI application
│   ├── app/                   # Application code
│   │   ├── api/              # API routes
│   │   ├── models/           # Database models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── workers/          # Celery tasks
│   ├── alembic/              # Database migrations
│   ├── tests/                # Test suite
│   ├── Dockerfile            # Production image
│   └── pyproject.toml        # Dependencies
├── nginx/                     # Nginx configuration
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.dev.yml     # Development (DB only)
├── docker-compose.yml         # Production (external DB)
├── docker-compose.full.yml    # Standalone (all services)
├── Makefile                   # Common commands
├── quickstart.sh              # Quick setup script
└── DOCKER.md                  # Deployment guide
```

## Development Workflow

### Using Make Commands

```bash
# Start development environment
make dev

# View logs
make dev-logs

# Run migrations
make migrate-dev

# Open database shell
make shell-db-dev

# Stop development environment
make dev-stop
```

### Running Tests

```bash
cd backend
uv run pytest
```

### Database Migrations

```bash
# Create a new migration
cd backend
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## API Examples

### Upload a FIT File

```bash
curl -X POST "http://localhost:8000/api/v1/activities/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/ride.fit"
```

### Get Activity Details

```bash
curl "http://localhost:8000/api/v1/activities/{activity_id}"
```

### List Activities

```bash
curl "http://localhost:8000/api/v1/activities?skip=0&limit=10"
```

## Configuration

Key environment variables (see `.env.example` for all options):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async database connection | `postgresql+asyncpg://...` |
| `SYNC_DATABASE_URL` | Sync database connection | `postgresql+psycopg2://...` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `FIT_STORAGE_PATH` | FIT file storage location | `./data/fit_files` |
| `SECRET_KEY` | JWT signing key | (required) |
| `DEBUG` | Debug mode | `true` |

## Architecture

### Data Flow

1. **Upload**: User uploads FIT file via API
2. **Validation**: FastAPI validates file and creates activity record
3. **Processing**: Celery worker parses FIT file and extracts metrics
4. **Storage**: Time-series data stored in TimescaleDB, geospatial in PostGIS
5. **Analytics**: Background tasks compute derived metrics (power zones, etc.)
6. **API**: Cached results served via FastAPI

### Database Schema

- **activities**: Core activity metadata
- **activity_points**: Time-series GPS/sensor data (hypertable)
- **activity_laps**: Lap/segment summaries
- **activity_zones**: Power/HR zone distributions

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Add your license here]

## Acknowledgments

- FIT file parsing powered by [fitparse](https://github.com/dtcooper/python-fitparse)
- Time-series optimization by [TimescaleDB](https://www.timescale.com/)
- Geospatial features by [PostGIS](https://postgis.net/)
