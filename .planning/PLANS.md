# Execution Plans: Cycling Analytics Platform

**Created:** 2026-02-10
**Covers:** Phases 1-8
**Note:** Phases 9-11 (Xert algorithms, Season Planning) are deferred and will be planned when Phases 1-8 are complete.

> **IMPORTANT:** This monolithic file has been split into per-phase files for easier navigation.
>
> - Phase-specific plans are now located in `.planning/phases/{phase-name}/PLAN.md`
> - Cross-phase concerns are in `.planning/phases/CROSS-PHASE-CONCERNS.md`
> - This file remains as the complete reference but is no longer the primary source.
>
> See:
> - `.planning/phases/01-data-foundation/PLAN.md`
> - `.planning/phases/02-coggan-metrics/PLAN.md`
> - `.planning/phases/03-strava-integration/PLAN.md`
> - `.planning/phases/04-threshold-management/PLAN.md`
> - `.planning/phases/05-multi-user/PLAN.md`
> - `.planning/phases/06-frontend-foundation/PLAN.md`
> - `.planning/phases/07-activity-detail-views/PLAN.md`
> - `.planning/phases/08-dashboard-charts/PLAN.md`

---

## Phase 1: Data Foundation

**Goal**: User can import FIT files and store ride data with numerical precision in TimescaleDB hypertables
**Requirements**: DATA-01, DATA-03, DATA-04, DATA-05, INFR-02, INFR-03, INFR-04
**Dependencies**: None (first phase)

> **Key constraint**: PostgreSQL + TimescaleDB + PostGIS runs on the user's NAS, NOT in Docker. Docker Compose runs the FastAPI app, Celery worker, and Redis only. Dev environment runs Python locally with uv; Docker is only for services (Redis).

### Plan 1.1: Project Scaffolding and Backend Skeleton

**Description**: Initialize the Python backend project with uv, create the FastAPI application skeleton with config, health check, and project structure following the architecture spec.

**Files to create**:
- `backend/pyproject.toml` -- uv project config with all Phase 1 dependencies
- `backend/app/__init__.py`
- `backend/app/main.py` -- FastAPI app init, CORS, router includes, lifespan handler
- `backend/app/config.py` -- Pydantic Settings class loading from env vars (DATABASE_URL pointing to NAS, REDIS_URL, FIT_STORAGE_PATH, SECRET_KEY)
- `backend/app/routers/__init__.py`
- `backend/app/routers/health.py` -- GET /health (DB ping, Redis ping, disk space)
- `backend/app/services/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/workers/__init__.py`
- `backend/app/utils/__init__.py`
- `backend/app/dependencies.py` -- get_db session dependency
- `backend/tests/__init__.py`
- `backend/tests/conftest.py` -- pytest fixtures (test DB session, test client)
- `.env.example` -- template with all env vars documented
- `.gitignore` -- update with Python, venv, .env, __pycache__, .fit files

**Technical approach**:
- Use `uv init` then `uv add` for all dependencies: fastapi[standard], sqlalchemy[asyncio], asyncpg, psycopg2-binary, alembic, pydantic-settings, numpy, pandas, scipy, fitparse, celery, redis, python-multipart, aiofiles, structlog
- Dev deps: pytest, pytest-asyncio, httpx (for TestClient), ruff, mypy
- `psycopg2-binary`: sync PostgreSQL driver required by Celery workers (which cannot use async asyncpg)
- `structlog`: structured JSON logging for FastAPI and Celery (configured in lifespan handler)
- FastAPI lifespan context manager for startup/shutdown (DB pool, Redis connection)
- Config uses pydantic-settings with `.env` file support
- DATABASE_URL format: `postgresql+asyncpg://user:pass@NAS_IP:5432/cycling_analytics`
- SYNC_DATABASE_URL format: `postgresql+psycopg2://user:pass@NAS_IP:5432/cycling_analytics` (for Celery workers)
- REDIS_URL format: `redis://redis:6379/0` (broker=db0, results=db1, cache=db2)

**Acceptance criteria**:
- `uv sync` installs all dependencies without errors
- `uv run python -m app.main` starts FastAPI server on port 8000
- GET /health returns 200 with `{"status": "healthy", "database": "connected", "redis": "connected", "disk_free_gb": 142.7}` (disk_free_gb reports free space on FIT_STORAGE_PATH volume)
- GET /docs shows OpenAPI documentation
- `uv run pytest` runs (even if 0 tests) without errors

**Estimated complexity**: M

---

### Plan 1.2: Database Setup and Alembic Migrations

**Description**: Set up SQLAlchemy 2.1+ async engine connecting to the NAS-hosted PostgreSQL + TimescaleDB + PostGIS database. Create the initial Alembic migration with core tables and the activity_streams hypertable.

**Files to create**:
- `backend/app/database.py` -- async engine, async sessionmaker, sync engine (for Celery), Base declarative class
- `backend/alembic.ini` -- Alembic config pointing to DATABASE_URL from env
- `backend/alembic/env.py` -- async migration support, imports all models
- `backend/alembic/script.py.mako` -- migration template
- `backend/alembic/versions/001_initial_schema.py` -- initial migration

**Files to create (models)**:
- `backend/app/models/user.py` -- User model (id, email, password_hash, display_name, created_at, updated_at). Single user for now, multi-user in Phase 5.
- `backend/app/models/activity.py` -- Activity model (id, user_id FK, external_id, source enum[fit_upload/garmin/strava/manual/csv], activity_date TIMESTAMPTZ, name, sport_type, duration_seconds INT, distance_meters NUMERIC, elevation_gain_meters NUMERIC, avg_power_watts NUMERIC, max_power_watts NUMERIC, avg_hr INT, max_hr INT, avg_cadence INT, calories INT, tss NUMERIC nullable, np_watts NUMERIC nullable, intensity_factor NUMERIC nullable, fit_file_path TEXT nullable, device_name TEXT nullable, notes TEXT nullable, processing_status enum[pending/processing/complete/error], error_message TEXT nullable, created_at, updated_at)
- `backend/app/models/activity_stream.py` -- ActivityStream hypertable model (activity_id INT NOT NULL, timestamp TIMESTAMPTZ NOT NULL, elapsed_seconds INT, power_watts INT nullable, heart_rate INT nullable, cadence INT nullable, speed_mps NUMERIC nullable, altitude_meters NUMERIC nullable, distance_meters NUMERIC nullable, temperature_c NUMERIC nullable, position GEOGRAPHY(POINT,4326) nullable, grade_percent NUMERIC nullable). Primary key composite (activity_id, timestamp).
- `backend/app/models/activity_lap.py` -- ActivityLap model (id, activity_id FK, lap_index INT, start_time TIMESTAMPTZ, total_elapsed_time NUMERIC, total_distance NUMERIC nullable, avg_power NUMERIC nullable, max_power NUMERIC nullable, avg_heart_rate INT nullable, max_heart_rate INT nullable, avg_cadence INT nullable, created_at). Regular table (not hypertable -- laps are low-volume, ~10-50 per activity, accessed by activity_id not time range).
- `backend/app/models/health_metric.py` -- HealthMetric model for Garmin health data (id, user_id FK, date DATE, metric_type enum[sleep_score/weight_kg/resting_hr/hrv_ms/body_battery/stress_avg], value NUMERIC, source TEXT, raw_data JSONB nullable, created_at). Stored but not viewed until future phase.

**Technical approach**:
- SQLAlchemy async engine with asyncpg driver: `create_async_engine(DATABASE_URL)`
- SQLAlchemy sync engine with psycopg2 driver: `create_engine(SYNC_DATABASE_URL)` -- used by Celery workers for synchronous DB access
- Async session factory: `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
- Sync session factory: `sessionmaker(sync_engine)` -- for Celery workers
- All power/distance/elevation columns use `Numeric` (NUMERIC in PostgreSQL) per INFR-03
- GPS position uses `geoalchemy2.Geography('POINT', srid=4326)` per INFR-04
- Migration enables TimescaleDB extension, PostGIS extension, then creates hypertable:
  ```sql
  CREATE EXTENSION IF NOT EXISTS timescaledb;
  CREATE EXTENSION IF NOT EXISTS postgis;
  -- After creating activity_streams table:
  SELECT create_hypertable('activity_streams', 'timestamp',
    chunk_time_interval => INTERVAL '90 days',
    if_not_exists => TRUE
  );
  ```
- Compression policy on activity_streams: segmentby=activity_id, orderby=timestamp DESC, compress after 30 days (30 days keeps the most-analyzed recent data uncompressed; 7 days was too aggressive for a user actively reviewing last 2-4 weeks of rides)
- Indexes: activities(user_id, activity_date DESC), activity_streams(activity_id, timestamp), activities(external_id) for duplicate detection, activity_laps(activity_id, lap_index)
- Seed user: migration 001 inserts a default user (id=1, email='rider@localhost', display_name='Default Rider') so Phases 1-4 have a user_id to associate data with. Phase 5 adds proper auth and registration; until then, all API requests implicitly use this seed user.

**Acceptance criteria**:
- `alembic upgrade head` runs against NAS PostgreSQL without errors
- TimescaleDB hypertable verified: `SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'activity_streams'` returns 1 row
- PostGIS extension active: `SELECT PostGIS_Version()` returns version string
- All NUMERIC columns confirmed: no FLOAT/REAL/DOUBLE types in schema
- Compression policy active: `SELECT * FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression'` returns 1 row
- `activity_laps` table created with FK to activities: `SELECT count(*) FROM information_schema.tables WHERE table_name = 'activity_laps'` returns 1
- Seed user exists: `SELECT id, email FROM users WHERE id = 1` returns the default rider
- Sync engine connects successfully using SYNC_DATABASE_URL with psycopg2 driver
- Rollback works: `alembic downgrade base` cleans up without errors

**Estimated complexity**: L

---

### Plan 1.3: Docker Compose for Development and Deployment

**Description**: Create Docker Compose configuration for three environments: (1) development -- Redis only, Python runs locally with uv; (2) production with external DB -- FastAPI app, Celery worker, Redis, Nginx, connecting to NAS-hosted PostgreSQL; (3) standalone -- full stack including TimescaleDB + PostGIS for users without a NAS database. Supports both Docker-included and external database modes.

**Files to create**:
- `docker-compose.yml` -- production stack connecting to external NAS DB (api, worker, redis, nginx)
- `docker-compose.full.yml` -- standalone stack including TimescaleDB + PostGIS (api, worker, redis, nginx, db)
- `docker-compose.dev.yml` -- dev stack (redis only, ports exposed for local Python)
- `backend/Dockerfile` -- multi-stage build (uv install -> slim runtime)
- `nginx/nginx.conf` -- reverse proxy config (API on /api, future frontend on /)
- `nginx/Dockerfile` -- Nginx with custom config
- `.env.example` -- update with all required env vars

**Technical approach**:
- Production `docker-compose.yml`:
  ```yaml
  services:
    api:
      build: ./backend
      environment:
        - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}
        - REDIS_URL=redis://redis:6379/0
        - FIT_STORAGE_PATH=/data/fit_files
      volumes:
        - fit_storage:/data/fit_files
      depends_on:
        - redis
    worker:
      build: ./backend
      command: celery -A app.workers.celery_app worker -Q high_priority,low_priority -c 4 --loglevel=info
      environment:
        - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}
        - SYNC_DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}
        - REDIS_URL=redis://redis:6379/0
        - FIT_STORAGE_PATH=/data/fit_files
      volumes:
        - fit_storage:/data/fit_files
      depends_on:
        - redis
    redis:
      image: redis:7-alpine
      volumes:
        - redis_data:/data
    nginx:
      build: ./nginx
      ports:
        - "${APP_PORT:-80}:80"
      depends_on:
        - api
  ```
- `docker-compose.yml`: NO database service -- DB is external on NAS. DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME as env vars for NAS connection.
- `docker-compose.full.yml`: includes TimescaleDB + PostGIS service for standalone users who do not have an external NAS database:
  ```yaml
  services:
    db:
      image: timescale/timescaledb-ha:pg16
      environment:
        - POSTGRES_DB=cycling_analytics
        - POSTGRES_USER=cycling
        - POSTGRES_PASSWORD=${DB_PASS}
      volumes:
        - pgdata:/home/postgres/pgdata/data
      ports:
        - "5432:5432"
  ```
  All other services (api, worker, redis, nginx) are identical, with DATABASE_URL pointing to the `db` service.
- Dev compose: just Redis on localhost:6379
- Documentation note in `.env.example`: explain both modes -- "Use `docker compose up` for external NAS DB, or `docker compose -f docker-compose.full.yml up` for standalone with included database."
- Backend Dockerfile uses uv for dependency install (COPY pyproject.toml, uv.lock -> uv sync --frozen)
- FIT file storage as named Docker volume mounted to both api and worker

**Acceptance criteria**:
- `docker compose -f docker-compose.dev.yml up` starts Redis accessible on localhost:6379
- `docker compose up --build` starts app services (api, worker, redis, nginx), API accessible through Nginx with external NAS DB
- `docker compose -f docker-compose.full.yml up --build` starts full stack including TimescaleDB + PostGIS for standalone users
- GET http://localhost/api/health returns 200 with database connected (either external NAS or included DB)
- Worker logs show Celery connected to Redis broker
- FIT files persist across container restarts (volume mount verified)
- `docker compose down` cleanly stops all services

**Estimated complexity**: M

---

### Plan 1.4: Celery Worker Setup and Task Infrastructure

**Description**: Initialize Celery with Redis broker, create task infrastructure with priority queues, retry policies, and status tracking. Build the foundation that FIT parsing and metric computation tasks will use.

**Files to create**:
- `backend/app/workers/celery_app.py` -- Celery app init, config (broker=Redis, serializer=json, time limits, UTC)
- `backend/app/workers/tasks/__init__.py`
- `backend/app/services/task_service.py` -- task status queries, task result retrieval via API
- `backend/app/routers/tasks.py` -- GET /tasks/{task_id} status endpoint
- `backend/app/schemas/task.py` -- TaskStatus response schema (task_id, status, result, error, progress)

**Technical approach**:
- Celery config: broker=redis://redis:6379/0, backend=redis://redis:6379/1, json serializer, UTC, task_track_started=True, task_time_limit=600, task_soft_time_limit=540
- Redis database separation: db0=Celery broker, db1=Celery results, db2=application cache (prevents key collisions between Celery internals and app cache keys)
- Two queues: `high_priority` (user-uploaded FIT files) and `low_priority` (Garmin sync, reprocessing)
- Base task class with structured logging via structlog (user_id, activity_id, task_type)
- Environment variable `SYNC_DATABASE_URL` using `postgresql+psycopg2://` driver for Celery worker DB access (Celery workers use synchronous operations, cannot use asyncpg)
- Task status endpoint for frontend polling: GET /tasks/{task_id} returns {status: "PENDING"|"STARTED"|"SUCCESS"|"FAILURE", progress: 0-100, result: {...}}
- Retry policy: max_retries=3 with exponential backoff (2^retries seconds)
- Celery worker runs with sync SQLAlchemy engine (not async) per architecture guidance

**Acceptance criteria**:
- Celery worker starts and connects to Redis: `celery -A app.workers.celery_app worker --loglevel=info`
- Test task dispatched and completes: `parse_test.delay()` returns SUCCESS
- GET /tasks/{task_id} returns correct status progression (PENDING -> STARTED -> SUCCESS)
- Failed task shows error message in GET /tasks/{task_id}
- Worker respects time limits (task killed after 600s)

**Estimated complexity**: M

---

### Plan 1.5: FIT File Parser and Import Pipeline

**Description**: Build the FIT file parsing service using python-fitparse. Extract activity metadata and second-by-second stream data from FIT files, handling device variability and edge cases.

**Files to create**:
- `backend/app/utils/fit_parser.py` -- FIT file parsing wrapper: parse_fit_file(file_path) -> (ActivityData, list[StreamRecord], list[LapRecord])
- `backend/app/schemas/fit_data.py` -- Pydantic models for parsed FIT data: ActivityData, StreamRecord, LapRecord, FitParseResult, FitParseWarning
- `backend/tests/test_utils/test_fit_parser.py` -- Unit tests with real FIT file fixtures
- `backend/tests/fixtures/` -- directory for test FIT files (various Garmin devices)

**Technical approach**:
- Use python-fitparse (fitparse library) to read FIT files
- Extract from `record` messages: timestamp, power, heart_rate, cadence, speed, altitude, position_lat, position_long, distance, temperature, grade
- Extract from `session` messages: sport, total_elapsed_time, total_distance, total_ascent, avg_power, max_power, avg_heart_rate, max_heart_rate, avg_cadence, total_calories, device info
- Extract from `lap` messages: start_time, total_elapsed_time, total_distance, avg_power, max_power, avg_heart_rate, max_heart_rate
- Semicircle to degree conversion for Garmin GPS: `degrees = semicircles * (180 / 2^31)`
- Handle missing fields gracefully (indoor rides have no GPS, some devices lack cadence)
- Power spike detection: flag values > 2500W as potential errors, still store them
- Zero power handling: distinguish between "no power meter" (null) and "coasting" (0)
- Parse warnings collected as list (not exceptions): device-specific fields ignored, unknown message types skipped
- Return structured result with warnings list for partial import support

**Acceptance criteria**:
- Parses Garmin Edge FIT file: extracts metadata + all stream fields
- Parses Garmin Forerunner FIT file: handles missing power field gracefully
- Indoor ride (no GPS): position fields null, no errors
- Corrupted FIT file: returns partial data with warning list, does not crash
- GPS coordinates correct: verified semicircle conversion against known locations (spot-check lat/lng)
- Timestamps in UTC
- Unit tests pass for each device type fixture

**Estimated complexity**: L

---

### Plan 1.6: Activity Upload API and Storage Pipeline

**Description**: Build the complete upload flow: API endpoint receives FIT file, stores it permanently, queues Celery task for parsing, parser extracts data, stores activity metadata in activities table and stream data in activity_streams hypertable via bulk insert.

**Files to create**:
- `backend/app/routers/activities.py` -- POST /activities/upload-fit (file upload), GET /activities (list), GET /activities/{id} (detail), DELETE /activities/{id}
- `backend/app/schemas/activity.py` -- ActivityCreate, ActivityResponse, ActivityListResponse, ActivityUploadResponse (with task_id)
- `backend/app/services/import_service.py` -- orchestrates upload: save file, create activity record (pending), queue parse task
- `backend/app/services/storage_service.py` -- file storage: save FIT to disk, generate unique path, cleanup on delete
- `backend/app/workers/tasks/fit_import.py` -- Celery task: parse_fit_file(activity_id, file_path) -> parse, bulk insert streams, update activity status
- `backend/tests/test_routers/test_activities.py` -- API integration tests
- `backend/tests/test_services/test_import_service.py` -- service unit tests

**Technical approach**:
- Upload validation (before processing):
  - File size: reject files > 50MB (FIT files are typically 1-5MB; generous limit for safety)
  - File type: verify FIT magic bytes (first 4 bytes), not just file extension
  - Rate limiting: 20 uploads per hour per IP (before auth in Phases 1-4) to prevent abuse
- Upload endpoint accepts multipart file upload (python-multipart)
- File storage: `{FIT_STORAGE_PATH}/{user_id}/{YYYY}/{MM}/{uuid}.fit` -- preserves originals per DATA-05
- Duplicate detection: fingerprint = SHA256 hash of FIT file content; check before creating activity
- Also check for timestamp + device_name match as secondary duplicate detection
- Multiple-device-same-ride detection: flag activities with overlapping timestamps and similar duration from different devices as potential duplicates (log warning, do not auto-merge; user resolves manually in future phase)
- Import service flow:
  1. Receive file -> compute hash -> check duplicates
  2. Save to permanent storage
  3. Create activity record with status=pending
  4. Queue Celery task on high_priority queue
  5. Return activity_id + task_id
- Celery task flow:
  1. Update activity status=processing
  2. Parse FIT file using fit_parser utility
  3. Update activity metadata from parsed session data
  4. Bulk insert stream records into activity_streams hypertable (batch of 1000 rows per INSERT for performance)
  5. Insert GPS route data with PostGIS GEOGRAPHY points
  6. Insert lap records into activity_laps table (parsed lap data from FIT file)
  7. Update activity status=complete (or status=error with error_message)
- Bulk insert using SQLAlchemy `insert().values(rows)` with sync engine in Celery worker
- Activity list endpoint: paginated (limit/offset), sorted by activity_date DESC, includes processing_status

**Acceptance criteria**:
- POST /activities/upload-fit with .fit file returns 202 with {activity_id, task_id}
- POST /activities/upload-fit with file > 50MB returns 413 Payload Too Large
- POST /activities/upload-fit with non-FIT file (wrong magic bytes) returns 400 Bad Request
- POST /activities/upload-fit returns 429 Too Many Requests after 20 uploads/hour from same IP
- After worker processes: GET /activities/{id} returns complete activity metadata
- Lap data stored: `SELECT count(*) FROM activity_laps WHERE activity_id = X` matches FIT lap count
- Stream data stored: `SELECT count(*) FROM activity_streams WHERE activity_id = X` matches FIT record count
- GPS coordinates stored as PostGIS GEOGRAPHY: `SELECT ST_AsText(position) FROM activity_streams WHERE activity_id = X AND position IS NOT NULL LIMIT 1` returns POINT(lng lat)
- Duplicate upload returns 409 Conflict with existing activity_id
- Original FIT file exists at expected storage path
- DELETE /activities/{id} removes activity, streams, and FIT file
- GET /activities returns paginated list sorted by date
- All NUMERIC columns in DB verified (no float storage)

**Estimated complexity**: L

---

### Plan 1.7: Zip Archive and Bulk Import Support

**Description**: Extend the import pipeline to handle zip archives (Garmin bulk export), multiple file uploads, and directory-style batch processing. Add progress tracking for bulk operations.

**Files to create**:
- `backend/app/routers/imports.py` -- POST /imports/archive (zip upload), POST /imports/bulk (multiple files), POST /imports/directory (server-side directory import with path parameter), GET /imports/{batch_id}/status (batch progress)
- `backend/app/schemas/import_batch.py` -- ImportBatchResponse, ImportBatchStatus, ImportItemStatus
- `backend/app/services/batch_import_service.py` -- extract zip, iterate files, queue individual parse tasks, track batch progress
- `backend/app/models/import_batch.py` -- ImportBatch model (id, user_id, total_files, processed_files, failed_files, status, created_at)
- `backend/alembic/versions/002_import_batch_table.py` -- migration for import_batch table
- `backend/tests/test_services/test_batch_import.py`

**Technical approach**:
- Zip archive handling: extract to temp dir, find all .fit files recursively, process each
- Garmin data export format: typically `DI_CONNECT/DI-Connect-Fitness/FileName-*.fit` structure
- Batch import creates ImportBatch record, then queues individual parse_fit_file tasks per file
- Progress tracked via batch record: total_files, processed_files (callback from each task), failed_files
- Batch status endpoint returns per-file status: `{total: 1500, processed: 342, failed: 2, items: [{file: "...", status: "complete"}, ...]}`
- Duplicate detection applies per-file within batch (skip already-imported files)
- Memory management: extract zip in streaming fashion, don't load entire archive into memory
- Directory import: `POST /imports/directory` accepts a server-side path parameter (e.g., `/mnt/nas/garmin-export/`), scans for .fit files recursively, and processes them through the same batch pipeline. This supports server-side imports where files are already on the NAS without requiring HTTP upload.
- Rate limit batch processing: max 10 concurrent parse tasks per batch to avoid overwhelming DB

**Acceptance criteria**:
- Upload Garmin export zip: all FIT files extracted and queued
- GET /imports/{batch_id}/status shows progress (processed/total)
- Duplicate files in archive are skipped with status=skipped
- Corrupted files in archive are flagged with status=error, other files still process
- 100+ file zip processes without memory issues
- Batch completes with accurate final count (processed + skipped + failed = total)

**Estimated complexity**: M

---

### Plan 1.8: Garmin Connect Automated Sync

**Description**: Implement automated sync with Garmin Connect using the unofficial garminconnect Python library. Pull new activities as FIT files and health data (sleep, weight, HRV, resting HR).

**Files to create**:
- `backend/app/services/garmin_service.py` -- Garmin Connect client wrapper: login, fetch activity list, download FIT file, fetch health metrics
- `backend/app/workers/tasks/garmin_sync.py` -- Celery periodic task: check for new activities, download and import
- `backend/app/models/integration.py` -- Integration model (id, user_id, provider enum[garmin/strava], credentials_encrypted BYTEA, last_sync_at, sync_enabled BOOLEAN, status, error_message)
- `backend/app/routers/integrations.py` -- POST /integrations/garmin/connect (save credentials), POST /integrations/garmin/sync (manual trigger), GET /integrations/garmin/status, DELETE /integrations/garmin/disconnect
- `backend/app/schemas/integration.py` -- GarminConnectRequest, IntegrationStatus
- `backend/alembic/versions/003_integrations_table.py` -- migration
- `backend/tests/test_services/test_garmin_service.py`

**Technical approach**:
- Use `garminconnect` library (pip: garminconnect): authenticate with email/password, session-based
- Store encrypted credentials (Fernet symmetric encryption with key from config)
- Sync flow:
  1. Login to Garmin Connect
  2. Fetch activity list since last_sync_at
  3. For each new activity: download FIT file, pipe into existing import pipeline
  4. Update last_sync_at
- Health data sync: fetch daily sleep score, weight, resting HR, HRV status, body battery
- Store health data in health_metrics table (user_id, date, metric_type, value)
- Celery Beat periodic task: check every 30 minutes for new activities
- Error handling: Garmin session expiry (re-login), rate limiting (back off), API changes (log and skip)
- Manual sync endpoint for user-triggered full sync
- Health data views deferred -- just store for now

**Acceptance criteria**:
- User can save Garmin credentials via API (encrypted at rest)
- Manual sync trigger downloads new FIT files since last sync
- Downloaded FIT files go through existing import pipeline (duplicate detection applies)
- Health metrics stored: weight, sleep, HRV records appear in health_metrics table
- Sync errors logged with meaningful messages (not raw stack traces)
- Periodic sync runs every 30 minutes when enabled
- Garmin disconnect clears credentials and disables sync

**Estimated complexity**: L

---

### Plan 1.9: Manual Activity Entry and CSV Import

**Description**: Build manual activity entry for rides without FIT files (pre-GPS era, indoor trainer without recording) and CSV bulk import for historical data migration.

**Files to create**:
- `backend/app/routers/activities.py` -- extend with POST /activities/manual (manual entry), POST /activities/import-csv (CSV upload)
- `backend/app/schemas/activity.py` -- extend with ManualActivityCreate (date, duration, distance, avg_power, avg_hr, elevation_gain, notes)
- `backend/app/services/csv_import_service.py` -- parse CSV, validate rows, create activity records
- `backend/app/schemas/csv_import.py` -- CsvImportResponse, CsvRowError
- `backend/tests/test_services/test_csv_import.py`
- `backend/tests/fixtures/sample_activities.csv` -- test CSV fixture

**Technical approach**:
- Manual entry: creates activity with source=manual, no stream data, summary stats only
- Manual activities still participate in CTL/ATL/TSB calculations (using avg_power for TSS estimation)
- CSV format: date, duration_minutes, distance_km, avg_power_watts, avg_hr, elevation_gain_m, sport_type, notes
- CSV import: validate each row, create activities in batch, report per-row errors
- CSV uses pandas.read_csv for robust parsing (handles various date formats, missing columns)
- Duplicate detection for manual entries: same user + same date + same duration = prompt for confirmation
- No stream data for manual/CSV entries -- these are summary-only activities

**Acceptance criteria**:
- POST /activities/manual creates activity with source=manual
- Manual activity appears in activity list alongside FIT-imported activities
- CSV with 100 rows imports successfully, creates 100 activities
- CSV with errors: valid rows import, invalid rows returned with error details
- Duplicate date+duration detection works (returns warning, not auto-reject)
- Manual activities have no stream data (GET /activities/{id}/streams returns empty)

**Estimated complexity**: S

---

### Plan 1.10: Activity Streams API and Data Access Layer

**Description**: Build API endpoints for accessing second-by-second stream data and activity route data. These endpoints serve the frontend in later phases.

**Files to create**:
- `backend/app/routers/streams.py` -- GET /activities/{id}/streams (full stream data), GET /activities/{id}/streams/summary (downsampled for charts)
- `backend/app/routers/routes.py` -- GET /activities/{id}/route (GeoJSON route)
- `backend/app/routers/activities.py` -- extend with GET /activities/{id}/fit-file (download original FIT file), GET /activities/export-csv (export activity list as CSV)
- `backend/app/schemas/stream.py` -- StreamResponse, StreamSummaryResponse, StreamDataPoint
- `backend/app/schemas/route.py` -- RouteGeoJSON
- `backend/app/services/stream_service.py` -- fetch streams with optional downsampling, generate GeoJSON from PostGIS
- `backend/tests/test_routers/test_streams.py`
- `backend/tests/test_routers/test_routes.py`

**Technical approach**:
- Full streams endpoint: returns all data points for an activity (can be 3600+ rows per hour)
- Summary endpoint: downsamples to N points (default 500) using LTTB algorithm (Largest Triangle Three Buckets) for chart display -- preserves peaks/valleys better than naive sampling
- Route GeoJSON endpoint: `SELECT ST_AsGeoJSON(ST_MakeLine(position ORDER BY timestamp)) FROM activity_streams WHERE activity_id = X AND position IS NOT NULL`
- Response format for streams: `{timestamps: [...], power: [...], heart_rate: [...], cadence: [...], ...}` -- columnar format is more efficient than row-based for charting
- Pagination not needed for streams (bounded by activity duration, typically <20K rows)
- Include basic stats in stream response: min/max/avg for each field
- FIT file download: `GET /activities/{id}/fit-file` returns the original FIT file as `application/octet-stream` with Content-Disposition attachment header. Returns 404 if activity has no FIT file (manual entry). File is already stored (Plan 1.6), this just serves it.
- Activity list CSV export: `GET /activities/export-csv` returns a CSV file with columns: date, name, sport_type, duration, distance, avg_power, max_power, avg_hr, tss, np, if, source. Supports optional date range query params. Content-Type: text/csv.

**Acceptance criteria**:
- GET /activities/{id}/streams returns complete time-series data
- GET /activities/{id}/streams/summary?points=500 returns downsampled data with 500 points
- Downsampled data preserves power peaks (max power in summary equals max power in full data)
- GET /activities/{id}/route returns valid GeoJSON LineString
- Indoor activity route endpoint returns 404 or empty GeoJSON (no GPS data)
- GET /activities/{id}/fit-file returns the original FIT file (Content-Type: application/octet-stream)
- GET /activities/{id}/fit-file for manual entry returns 404
- GET /activities/export-csv returns valid CSV with all activity columns
- Response time < 500ms for 2-hour ride stream data

**Estimated complexity**: M

---

### Phase 1 Verification

Run these checks to verify Phase 1 is complete:

```bash
# 1. Backend starts and is healthy
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","redis":"connected","disk_free_gb":142.7}

# 2. Database schema is correct
psql $DATABASE_URL -c "SELECT * FROM timescaledb_information.hypertables;"
psql $DATABASE_URL -c "SELECT PostGIS_Version();"
psql $DATABASE_URL -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'activities' AND column_name IN ('tss','distance_meters','elevation_gain_meters');"
# Expected: all should be 'numeric'

# 3. FIT file upload works
curl -X POST http://localhost:8000/activities/upload-fit -F "file=@test_ride.fit"
# Expected: 202 with activity_id and task_id

# 4. Activity data stored correctly
curl http://localhost:8000/activities
# Expected: activity list with imported ride

# 5. Stream data stored
curl http://localhost:8000/activities/1/streams | python -c "import sys,json; d=json.load(sys.stdin); print(f'Streams: {len(d[\"timestamps\"])} points')"
# Expected: matches FIT file record count

# 6. Route data as GeoJSON
curl http://localhost:8000/activities/1/route
# Expected: valid GeoJSON with coordinates

# 7. Docker deployment works
docker compose up --build -d
curl http://localhost/api/health
# Expected: healthy through Nginx proxy

# 8. All tests pass
cd backend && uv run pytest -v
```

---

## Phase 2: Coggan Metrics Engine

**Goal**: User sees accurate TSS, NP, CTL/ATL/TSB calculations for every ride
**Requirements**: METR-01, METR-02, METR-03, METR-04, METR-05, METR-06, METR-07
**Dependencies**: Phase 1

### Plan 2.1: Normalized Power (NP) Calculation

**Description**: Implement the Normalized Power algorithm with proper edge case handling for short rides, power dropouts, and extreme spikes.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- NP calculation function, power zone utilities
- `backend/app/schemas/metrics.py` -- NormalizedPowerResult, PowerZoneDistribution
- `backend/tests/test_utils/test_coggan_model.py` -- extensive NP tests with edge cases

**Technical approach**:
- NP algorithm (Coggan standard):
  1. Calculate 30-second rolling average of power
  2. Raise each averaged value to the 4th power
  3. Take the mean of all raised values
  4. Take the 4th root of the mean
- Implementation uses NumPy arrays for performance: `np.convolve` for rolling average, vectorized power/root operations
- Calculations use NumPy float64 for performance; final results rounded to 1 decimal place and stored as PostgreSQL NUMERIC (float64 has ~15-17 significant digits, worst-case error for cycling power data is sub-0.01W, which is negligible)
- Edge cases:
  - Short rides (<30 seconds): return average power (not enough data for rolling average)
  - Power dropouts (value=0): include zeros in rolling average (coasting is valid)
  - Missing power (null): exclude from calculation window, note gap
  - Extreme spikes (>2500W): include but flag for review (legitimate sprints exist)
  - Rides with <50% power data coverage: calculate but flag as low confidence
- Return structured result with confidence flag and warnings

**Acceptance criteria**:
- NP for a steady 200W ride = ~200W (within 1W)
- NP for variable power ride > average power (as expected)
- Short ride (<30s) returns average power with warning
- Ride with dropouts handles zeros correctly
- All calculations use NUMERIC precision (verify no float intermediate storage)
- Test against known NP values from TrainingPeaks/intervals.icu reference

**Estimated complexity**: M

---

### Plan 2.2: TSS, IF, and Power Zones

**Description**: Implement Training Stress Score (TSS), Intensity Factor (IF), and 7-zone Coggan power zone classification.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- extend with TSS, IF calculation, power zone functions
- `backend/app/models/user_settings.py` -- UserSettings model (user_id, ftp_watts NUMERIC, ftp_method enum, ftp_updated_at, hr_zones JSONB nullable, weight_kg NUMERIC nullable)
- `backend/app/routers/settings.py` -- minimal FTP endpoints: POST /settings/ftp (set FTP value), GET /settings/ftp (get current FTP). This unblocks Phase 2 verification; full settings management is in Plan 4.5.
- `backend/app/schemas/settings.py` -- FtpSetting (ftp_watts: Decimal)
- `backend/alembic/versions/004_user_settings.py` -- migration
- `backend/tests/test_utils/test_tss_if.py`
- `backend/tests/test_routers/test_settings_ftp.py`

**Technical approach**:
- Intensity Factor: `IF = NP / FTP`
- TSS: `TSS = (duration_seconds * NP * IF) / (FTP * 3600) * 100`
- Coggan 7-zone model (percentage of FTP):
  - Zone 1 (Active Recovery): <55%
  - Zone 2 (Endurance): 55-75%
  - Zone 3 (Tempo): 76-90%
  - Zone 4 (Lactate Threshold): 91-105%
  - Zone 5 (VO2max): 106-120%
  - Zone 6 (Anaerobic Capacity): 121-150%
  - Zone 7 (Neuromuscular): >150%
- Zone time distribution: calculate seconds spent in each zone for an activity
- UserSettings stores current FTP (manual entry for now, auto-estimation in Phase 4)
- TSS stored on activity record after computation (cached)
- For manual entries without stream data: estimate TSS from avg_power and duration using IF approximation

**Acceptance criteria**:
- TSS for 1-hour ride at FTP = 100 (by definition)
- TSS for 1-hour ride at 75% FTP ~ 56 (0.75^2 * 100)
- IF correctly reflects ratio to FTP
- Power zone boundaries match standard Coggan zones
- Zone distribution sums to total ride time
- Manual entry TSS estimation reasonable (within 10% of actual for steady rides)
- POST /settings/ftp with `{"ftp_watts": 280}` stores FTP value
- GET /settings/ftp returns current FTP value

**Estimated complexity**: M

---

### Plan 2.3: Metric Computation Pipeline

**Description**: Build the background metric computation pipeline that automatically calculates NP, TSS, IF, and zone distribution when an activity is imported, and recalculates when FTP changes.

**Files to create**:
- `backend/app/workers/tasks/metric_computation.py` -- Celery task: compute_activity_metrics(activity_id), recompute_all_metrics(user_id)
- `backend/app/services/compute_service.py` -- orchestrates metric calculation: fetch streams, compute NP/TSS/IF/zones, store results
- `backend/app/models/activity_metrics.py` -- ActivityMetrics model (activity_id FK, ftp_at_computation NUMERIC, normalized_power NUMERIC, tss NUMERIC, intensity_factor NUMERIC, zone_distribution JSONB, variability_index NUMERIC, efficiency_factor NUMERIC nullable, computed_at TIMESTAMPTZ)
- `backend/alembic/versions/005_activity_metrics.py` -- migration
- `backend/tests/test_services/test_compute_service.py`

**Technical approach**:
- Computation triggered automatically after FIT import completes (chained Celery task)
- compute_activity_metrics(activity_id):
  1. Fetch stream data for activity
  2. Fetch user's current FTP (or FTP at ride time if stored)
  3. Calculate NP, IF, TSS, zone distribution
  4. Calculate variability index (NP / avg_power)
  5. Calculate efficiency factor (NP / avg_HR) if HR data available
  6. Store in activity_metrics table
  7. Update activity summary fields (tss, np_watts, intensity_factor)
- recompute_all_metrics(user_id): triggered when FTP changes
  1. Queue on low_priority queue
  2. Fetch all activities for user
  3. Recompute each (incremental: skip if FTP unchanged for that date)
  4. Track progress in batch record
- Store ftp_at_computation with each metric record for audit trail
- Metrics are replaced on recomputation (no versioning per CONTEXT.md decision)

**Acceptance criteria**:
- Uploading a FIT file automatically triggers metric computation
- Activity metrics table populated after computation
- Activity summary fields (tss, np_watts, IF) updated
- FTP change triggers recomputation of all activities
- Recomputation updates metrics and summary fields
- Metrics for manual entries calculated from summary data
- Computation completes within 5 seconds per activity

**Estimated complexity**: M

---

### Plan 2.4: CTL/ATL/TSB Fitness Tracking

**Description**: Implement Chronic Training Load (CTL, 42-day), Acute Training Load (ATL, 7-day), and Training Stress Balance (TSB) using exponentially weighted moving averages.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- extend with CTL/ATL/TSB calculation functions
- `backend/app/models/fitness_metrics.py` -- DailyFitness model (user_id, date DATE, tss_total NUMERIC, ctl NUMERIC, atl NUMERIC, tsb NUMERIC, activity_count INT, threshold_method VARCHAR default 'manual'). Primary key (user_id, date, threshold_method).
- `backend/app/services/fitness_service.py` -- calculate and store daily fitness metrics, handle rest days (TSS=0)
- `backend/app/routers/metrics.py` -- GET /metrics/fitness?start_date=&end_date= (CTL/ATL/TSB time series)
- `backend/app/schemas/metrics.py` -- extend with FitnessDataPoint, FitnessTimeSeries
- `backend/alembic/versions/006_daily_fitness.py` -- migration
- `backend/tests/test_utils/test_fitness.py`
- `backend/tests/test_services/test_fitness_service.py`

**Technical approach**:
- Exponentially weighted moving average formulas:
  - `CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) * (1 - exp(-1/42))`
  - `ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) * (1 - exp(-1/7))`
  - `TSB_today = CTL_today - ATL_today` (positive = fresh, negative = fatigued)
- Rest days (no activity): TSS_today = 0, still apply decay formula
- Multiple activities per day: sum TSS values
- Implementation:
  1. After activity metrics computed, call fitness_service.update_from_date(user_id, activity_date)
  2. Fetch previous day's CTL/ATL
  3. Compute forward from activity_date to today, filling rest days
  4. Store daily_fitness rows for each day
- Incremental update: only recalculate from the changed date forward (not entire history)
- Full rebuild: for initial import of 1500+ rides, calculate entire history once (background task)
- API returns time series: list of {date, ctl, atl, tsb} points for chart rendering

**Acceptance criteria**:
- After importing rides: GET /metrics/fitness returns CTL/ATL/TSB time series
- Rest days show CTL/ATL decay (values decrease toward 0)
- TSB positive after rest, negative after hard block
- New activity upload incrementally updates fitness from that date forward
- Full history rebuild for 1500 rides completes within 30 seconds
- CTL after 42 days of 100 TSS/day ~ 63.2 (1 - 1/e) * 100
- CTL/ATL/TSB values stored as NUMERIC in database

**Estimated complexity**: L

---

### Plan 2.5: Metrics API and Cache Layer

**Description**: Build comprehensive metrics API endpoints with Redis caching for fast dashboard loads. Includes per-activity metrics retrieval and aggregated fitness data.

**Files to create**:
- `backend/app/routers/metrics.py` -- extend with GET /metrics/activities/{id} (single activity metrics), GET /metrics/summary (period summary)
- `backend/app/services/cache_service.py` -- Redis cache wrapper: get/set with TTL, cache key generation, invalidation patterns
- `backend/app/schemas/metrics.py` -- extend with ActivityMetricsResponse, PeriodSummary
- `backend/tests/test_services/test_cache_service.py`
- `backend/tests/test_routers/test_metrics.py`

**Technical approach**:
- Cache strategy (read-through):
  1. Check Redis for cached result (key: `fitness:{user_id}:{threshold_method}:{date_range}`)
  2. Cache miss: query daily_fitness table, serialize, store in Redis with 5-min TTL
  3. Cache invalidation: DEL keys on activity import, FTP change, or metric recomputation
- Per-activity metrics endpoint: returns NP, TSS, IF, zone distribution, VI, EF
- Period summary endpoint: total TSS, ride count, total duration, total distance for a date range
- Redis cache keys:
  - `fitness:{user_id}:manual` -- fitness time series (default threshold method for now)
  - `metrics:{activity_id}` -- per-activity metrics
  - `summary:{user_id}:{start}:{end}` -- period summaries
- Cache invalidation triggered by:
  - Activity import: invalidate fitness and summary caches for user
  - FTP change: invalidate all user caches
  - Activity delete: invalidate all user caches

**Acceptance criteria**:
- GET /metrics/fitness returns data within 100ms (cache hit)
- First request < 2 seconds (cache miss, DB query)
- Subsequent requests < 50ms (Redis cache)
- Cache invalidated on new activity import (fresh data within 5 min)
- Per-activity metrics endpoint returns all computed values
- Period summary returns correct aggregates

**Estimated complexity**: M

---

### Phase 2 Verification

```bash
# 1. Upload a FIT file and verify metrics calculated
curl -X POST http://localhost:8000/activities/upload-fit -F "file=@test_ride.fit"
# Wait for processing...
curl http://localhost:8000/metrics/activities/1
# Expected: {"normalized_power": 215, "tss": 87.3, "intensity_factor": 0.82, "zone_distribution": {...}}

# 2. Check fitness tracking
curl "http://localhost:8000/metrics/fitness?start_date=2025-01-01&end_date=2026-02-10"
# Expected: time series with ctl, atl, tsb values for each day

# 3. Verify power zones
curl http://localhost:8000/metrics/activities/1
# Expected: zone_distribution with seconds per zone, sums to ride duration

# 4. Set FTP and verify recalculation
curl -X POST http://localhost:8000/settings/ftp -d '{"ftp_watts": 280}'
# Wait for recomputation...
curl http://localhost:8000/metrics/activities/1
# Expected: TSS and IF updated based on new FTP

# 5. Run tests
cd backend && uv run pytest tests/test_utils/test_coggan_model.py -v
cd backend && uv run pytest tests/test_services/test_fitness_service.py -v
```

---

## Phase 3: Strava Integration

**Goal**: User can connect Strava account and automatically import activities via webhooks
**Requirements**: DATA-02
**Dependencies**: Phase 2

### Plan 3.1: Strava OAuth2 Flow

**Description**: Implement Strava OAuth2 authorization code flow so users can connect their Strava account to the application.

**Files to create**:
- `backend/app/services/strava_service.py` -- Strava OAuth2 client: build auth URL, exchange code for tokens, refresh tokens
- `backend/app/routers/integrations.py` -- extend with GET /integrations/strava/authorize (redirect to Strava), GET /integrations/strava/callback (exchange code), DELETE /integrations/strava/disconnect
- `backend/app/models/integration.py` -- extend with Strava-specific fields (access_token_encrypted, refresh_token_encrypted, token_expires_at, athlete_id)
- `backend/alembic/versions/007_strava_integration.py` -- migration for Strava token fields
- `backend/app/schemas/integration.py` -- extend with StravaAuthUrl, StravaCallbackResponse
- `backend/tests/test_services/test_strava_service.py`

**Technical approach**:
- Use stravalib library for API interactions
- OAuth2 flow:
  1. GET /integrations/strava/authorize: generate Strava auth URL with scopes (read,activity:read_all), redirect user
  2. User authorizes on Strava, redirected to callback URL
  3. GET /integrations/strava/callback?code=XXX: exchange code for access_token + refresh_token
  4. Store tokens encrypted (Fernet) in integration record
  5. Store Strava athlete_id for deduplication
- Token refresh: access tokens expire (6 hours), refresh automatically before API calls
- Scopes needed: `read,activity:read_all` (read public and private activities)
- Store STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in env vars

**Acceptance criteria**:
- User clicks "Connect Strava" -> redirected to Strava authorization page
- After authorizing -> redirected back with tokens stored
- GET /integrations/strava/status shows connected with athlete info
- Token refresh works when access token expired
- Disconnect removes tokens from database

**Estimated complexity**: M

---

### Plan 3.2: Strava Activity Sync

**Description**: Fetch activities from Strava API, download detailed stream data, and import through the existing pipeline.

**Files to create**:
- `backend/app/services/strava_service.py` -- extend with fetch_activities_since(last_sync), fetch_activity_streams(activity_id), fetch_activity_detail(activity_id)
- `backend/app/workers/tasks/strava_sync.py` -- Celery tasks: sync_strava_activities(user_id), fetch_strava_activity(user_id, strava_activity_id)
- `backend/app/services/strava_rate_limiter.py` -- rate limit tracker: 200 requests/15min, 2000/day, exponential backoff on 429
- `backend/tests/test_services/test_strava_sync.py`

**Technical approach**:
- Sync flow:
  1. Fetch activity list from Strava (paginated, since last_sync_at)
  2. For each activity: check if already imported (external_id match)
  3. For new activities: fetch detailed streams (time, watts, heartrate, cadence, velocity_smooth, altitude, latlng, distance)
  4. Convert Strava data format to internal format (same as FIT parser output)
  5. Create activity record with source=strava
  6. Bulk insert stream data into activity_streams hypertable
  7. Trigger metric computation (same pipeline as FIT import)
  8. Update integration.last_sync_at
- Rate limiting:
  - Track requests per 15-min window and per day
  - Before each request: check if limits would be exceeded
  - On 429 response: read Retry-After header, sleep, retry
  - Exponential backoff: 1s, 2s, 4s, 8s, max 60s
- Strava streams may not have power data (not all users have power meters): handle gracefully
- GPS data from Strava is already in degrees (no semicircle conversion needed)
- Manual sync endpoint: POST /integrations/strava/sync triggers full sync

**Acceptance criteria**:
- After connecting Strava: manual sync imports recent activities
- Activities appear with source=strava in activity list
- Stream data stored correctly (power, HR, GPS, etc.)
- Metrics automatically computed after sync
- Duplicate activities not re-imported
- Rate limits respected (no 429 errors in normal operation)
- Activities without power data import successfully (power fields null)

**Estimated complexity**: L

---

### Plan 3.3: Strava Webhook Subscription

**Description**: Set up Strava webhook subscription for real-time activity notifications. When a user uploads a ride to Strava, it automatically appears in our system.

**Files to create**:
- `backend/app/routers/webhooks.py` -- POST /webhooks/strava (event receiver), GET /webhooks/strava (subscription verification)
- `backend/app/services/strava_webhook_service.py` -- webhook validation, event routing
- `backend/app/workers/tasks/strava_sync.py` -- extend with process_strava_webhook(event_data) task
- `backend/tests/test_routers/test_webhooks.py`

**Technical approach**:
- Strava webhook subscription:
  1. Register webhook via Strava API (POST to strava.com/api/v3/push_subscriptions)
  2. Strava sends GET to callback URL with hub.challenge -- must respond with challenge value
  3. On new activity: Strava sends POST with {object_type: "activity", aspect_type: "create", object_id: 12345, owner_id: 67890}
- Webhook handler:
  1. Verify webhook signature (if Strava provides one)
  2. Look up user by Strava athlete_id (owner_id)
  3. Queue Celery task to fetch and import the activity
  4. Return 200 immediately (Strava requires fast response)
- Handle webhook events:
  - `create`: new activity -> fetch and import
  - `update`: activity edited -> re-fetch and update
  - `delete`: activity deleted on Strava -> optionally mark as deleted
- Webhook URL must be publicly accessible (for production: through Nginx/reverse proxy)
- For dev/testing: use ngrok or similar tunnel

**Acceptance criteria**:
- Strava webhook subscription created successfully
- GET /webhooks/strava responds to hub.challenge verification
- New Strava activity -> webhook received -> activity imported within 5 minutes
- Activity update webhook triggers re-import
- Webhook responds within 2 seconds (async processing)
- Invalid webhook payloads rejected

**Estimated complexity**: M

---

### Plan 3.4: Historical Strava Backfill

**Description**: Import all historical activities from Strava for users who connect their account. Handles large histories with rate limit awareness.

**Files to create**:
- `backend/app/services/strava_service.py` -- extend with backfill_all_activities(user_id)
- `backend/app/workers/tasks/strava_sync.py` -- extend with strava_historical_backfill(user_id) task
- `backend/app/routers/integrations.py` -- extend with POST /integrations/strava/backfill

**Technical approach**:
- Backfill fetches ALL activities from Strava (paginated, 200 per page, sorted by date)
- Rate limit aware: with 200 req/15min limit and needing 2 requests per activity (list + streams), can process ~100 activities per 15-min window
- For 1500 activities: approximately 30 minutes total (queued over multiple rate limit windows)
- Progress tracking: store backfill status in integration record (total_activities, imported, remaining)
- Deduplication: check external_id before importing each activity
- Queue on low_priority to avoid blocking real-time imports
- User can check progress via GET /integrations/strava/status

**Acceptance criteria**:
- Backfill imports all historical Strava activities
- Rate limits respected throughout (no 429 errors)
- Progress visible via status endpoint
- Pre-existing activities (from FIT upload) not duplicated
- Backfill can be interrupted and resumed (tracks last processed page)
- Completes for 1500 activities within ~45 minutes

**Estimated complexity**: M

---

### Phase 3 Verification

```bash
# 1. Strava OAuth flow
curl http://localhost:8000/integrations/strava/authorize
# Expected: redirect URL to Strava authorization page

# 2. After authorization callback
curl http://localhost:8000/integrations/strava/status
# Expected: {"connected": true, "athlete_id": 12345, "last_sync": null}

# 3. Manual sync
curl -X POST http://localhost:8000/integrations/strava/sync
# Expected: {"task_id": "...", "status": "queued"}

# 4. Webhook verification
curl "http://localhost:8000/webhooks/strava?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=STRAVA_VERIFY_TOKEN"
# Expected: {"hub.challenge": "test123"}

# 5. Activities imported from Strava
curl http://localhost:8000/activities?source=strava
# Expected: list of Strava-imported activities with metrics

# 6. Run tests
cd backend && uv run pytest tests/test_services/test_strava*.py -v
```

---

## Phase 4: Threshold Management

**Goal**: User can configure threshold estimation method and switch between views instantly
**Requirements**: THRS-01, THRS-02, THRS-03, THRS-05, THRS-06, THRS-07, THRS-08 (THRS-04 deferred to Phase 10 -- Xert threshold model requires Xert algorithms from Phase 9)
**Dependencies**: Phase 2

### Plan 4.1: Threshold Data Model and History

**Description**: Build the threshold management system that supports multiple estimation methods and stores threshold history over time.

**Files to create**:
- `backend/app/models/threshold.py` -- Threshold model (id, user_id FK, method enum[manual/pct_20min/pct_8min/xert_model], effective_date DATE, ftp_watts NUMERIC, source_activity_id FK nullable, is_active BOOLEAN, notes TEXT nullable, created_at). Unique constraint on (user_id, method, effective_date).
- `backend/app/models/activity_metrics.py` -- extend to include threshold_method and ftp_used_watts on each metric record
- `backend/app/routers/thresholds.py` -- CRUD endpoints: GET /thresholds (history), POST /thresholds (manual set), GET /thresholds/current (active by method), PUT /thresholds/{id}/activate
- `backend/app/schemas/threshold.py` -- ThresholdCreate, ThresholdResponse, ThresholdHistory, ThresholdMethodEnum
- `backend/alembic/versions/008_threshold_management.py` -- migration
- `backend/tests/test_routers/test_thresholds.py`

**Technical approach**:
- Threshold methods enum: manual, pct_20min (95% of 20-min best), pct_8min (90% of 8-min best), xert_model (dynamic, Phase 10)
- Each method maintains its own history: e.g., manual FTP set on 2025-01-01, auto-detected on 2025-01-15
- "Active method" stored in user_settings: which method is currently used for display
- Historical threshold lookup: `get_threshold_at_date(user_id, method, date)` returns the most recent threshold before that date
- ftp_at_ride_time stored per activity metric record for accurate retrospective analysis (THRS-08)
- Setting a new threshold does NOT retroactively change past metrics -- it only affects future computations and explicit recomputation requests

**Acceptance criteria**:
- POST /thresholds with method=manual creates threshold record
- GET /thresholds returns full history sorted by date
- GET /thresholds/current?method=manual returns most recent manual threshold
- Threshold lookup at specific date returns correct historical value
- Multiple methods can coexist (manual + auto-detected)

**Estimated complexity**: M

---

### Plan 4.2: Auto-Detection - 95% of 20-Minute Best

**Description**: Implement automatic threshold estimation using 95% of the best 20-minute power effort from ride history.

**Files to create**:
- `backend/app/services/threshold_service.py` -- threshold estimation logic
- `backend/app/utils/power_analysis.py` -- best_effort(streams, duration_seconds) function, mean_max_power calculations
- `backend/tests/test_utils/test_power_analysis.py`
- `backend/tests/test_services/test_threshold_service.py`

**Technical approach**:
- Best 20-minute power: sliding window over activity stream, find highest 20-minute average power
  - Use NumPy rolling mean: `np.convolve(power, np.ones(1200)/1200, mode='valid')`
  - Handle gaps (nulls) in power data: interpolate or skip windows with >10% missing data
- FTP estimate = best_20min * 0.95
- Search across ALL user activities: find the single best 20-minute effort
- Store as threshold with method=pct_20min, effective_date=date of best effort, source_activity_id=activity that contains the best effort
- Recalculate on new activity import (if new activity contains a better 20-min effort)
- Edge case: user with no rides >20 minutes -- cannot estimate, return null with message

**Acceptance criteria**:
- Given rides with known 20-min best power: estimate matches expected value within 1W
- Estimation updates when a new best 20-min effort is uploaded
- Activities shorter than 20 minutes are excluded
- Result links to source activity (which ride contains the best effort)
- No estimation for users without qualifying rides

**Estimated complexity**: M

---

### Plan 4.3: Auto-Detection - 90% of 8-Minute Best

**Description**: Implement threshold estimation using 90% of the best 8-minute power effort.

**Files to create**:
- `backend/app/utils/power_analysis.py` -- extend with 8-minute best effort
- `backend/app/services/threshold_service.py` -- extend with 8-minute estimation method
- `backend/tests/test_utils/test_power_analysis.py` -- extend

**Technical approach**:
- Same approach as Plan 4.2 but with 8-minute (480 second) window
- FTP estimate = best_8min * 0.90
- More rides qualify (8 min vs 20 min minimum duration)
- Store as threshold with method=pct_8min

**Acceptance criteria**:
- Given rides with known 8-min best power: estimate matches expected value
- Works for rides between 8-20 minutes where 20-min method would not
- Result links to source activity

**Estimated complexity**: S

---

### Plan 4.4: Multi-Method Metric Caching (THRS-06, THRS-07)

**Description**: Pre-compute and cache metrics for ALL threshold methods so users can switch views instantly without recalculation.

**Files to create**:
- `backend/app/services/compute_service.py` -- extend to compute metrics for all methods
- `backend/app/workers/tasks/metric_computation.py` -- extend with compute_all_methods(activity_id)
- `backend/app/routers/metrics.py` -- extend GET /metrics/fitness with ?threshold_method= query param
- `backend/app/services/fitness_service.py` -- extend to maintain per-method fitness series
- `backend/tests/test_services/test_multi_method.py`

**Technical approach**:
- When activity is imported, compute metrics for ALL available threshold methods:
  - For each method, look up threshold at ride date
  - Compute NP (same for all methods), TSS, IF, zones (different per method)
  - Store separate activity_metrics rows per method
  - Update daily_fitness rows per method
- API accepts `threshold_method` query parameter:
  - GET /metrics/fitness?threshold_method=manual (default)
  - GET /metrics/fitness?threshold_method=pct_20min
  - GET /metrics/activities/{id}?threshold_method=pct_8min
- Switching method in UI -> different API call -> instant results from cache
- Storage cost: ~3x current (one row per method per activity per day) -- acceptable for the use case
- When a new threshold is detected for any method: recompute affected metrics in background

**Acceptance criteria**:
- Activity metrics exist for all available methods after import
- GET /metrics/fitness?threshold_method=manual returns different values than ?threshold_method=pct_20min
- Switching method responds within 100ms (pre-cached)
- New threshold auto-detected -> affected metrics recomputed in background
- Daily fitness series maintained per method

**Estimated complexity**: L

---

### Plan 4.5: Threshold Method Selection and User Preferences

**Description**: Let users select their preferred threshold estimation method in profile settings. Selected method becomes the default for all views.

**Files to create**:
- `backend/app/routers/settings.py` -- GET /settings (user preferences), PUT /settings (update preferences)
- `backend/app/models/user_settings.py` -- extend with preferred_threshold_method, calendar_start_day, weight_kg, date_of_birth
- `backend/app/schemas/settings.py` -- UserSettingsResponse, UserSettingsUpdate
- `backend/tests/test_routers/test_settings.py`

**Technical approach**:
- User settings stored in user_settings table (one row per user)
- preferred_threshold_method defaults to 'manual'
- When user changes preferred method:
  1. Update user_settings.preferred_threshold_method
  2. Invalidate Redis caches for this user
  3. No recomputation needed (already pre-cached per Plan 4.4)
- API endpoints that return metrics use user's preferred method unless explicitly overridden by query param
- Settings page also stores: calendar_start_day (default Monday), weight_kg, units preference

**Acceptance criteria**:
- GET /settings returns current preferences
- PUT /settings updates preferred threshold method
- API endpoints default to user's preferred method
- Explicit ?threshold_method= overrides user preference
- Cache invalidated on preference change

**Estimated complexity**: S

---

### Phase 4 Verification

```bash
# 1. Set manual threshold
curl -X POST http://localhost:8000/thresholds -d '{"method":"manual","ftp_watts":275,"effective_date":"2026-01-01"}'

# 2. View auto-detected thresholds
curl http://localhost:8000/thresholds?method=pct_20min
# Expected: auto-detected FTP from best 20-min effort

# 3. Compare methods
curl "http://localhost:8000/metrics/fitness?threshold_method=manual"
curl "http://localhost:8000/metrics/fitness?threshold_method=pct_20min"
# Expected: different TSS/CTL values based on different FTP

# 4. Switch preferred method
curl -X PUT http://localhost:8000/settings -d '{"preferred_threshold_method":"pct_20min"}'
curl http://localhost:8000/metrics/fitness
# Expected: now defaults to pct_20min values

# 5. Verify instant switching (both should be < 100ms)
time curl "http://localhost:8000/metrics/fitness?threshold_method=manual"
time curl "http://localhost:8000/metrics/fitness?threshold_method=pct_20min"

# 6. Threshold history
curl http://localhost:8000/thresholds
# Expected: full history with multiple methods and dates

# 7. Run tests
cd backend && uv run pytest tests/test_services/test_threshold_service.py -v
cd backend && uv run pytest tests/test_services/test_multi_method.py -v
```

---

## Phase 5: Multi-User Infrastructure

**Goal**: Multiple users can securely access their own data with authentication
**Requirements**: INFR-01
**Dependencies**: Phase 1

### Plan 5.1: User Authentication with JWT

**Description**: Implement user registration, login, and JWT-based authentication with secure password hashing.

**Files to create**:
- `backend/app/routers/auth.py` -- POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout
- `backend/app/security.py` -- JWT encode/decode, password hashing (bcrypt), token verification dependency
- `backend/app/schemas/auth.py` -- RegisterRequest, LoginRequest, TokenResponse, UserResponse
- `backend/app/dependencies.py` -- extend with get_current_user dependency (JWT verification)
- `backend/tests/test_routers/test_auth.py`

**Technical approach**:
- Password hashing: passlib with bcrypt (or Argon2id via pwdlib for modern best practice)
- JWT tokens: PyJWT with HS256 signing, SECRET_KEY from env
- Token structure: {sub: user_id, exp: timestamp, iat: timestamp, type: "access"|"refresh"}
- Access token: 30-minute expiry
- Refresh token: 7-day expiry, stored in httpOnly cookie
- Login returns access_token in response body + refresh_token in httpOnly cookie
- Protected endpoints use `Depends(get_current_user)` -- extracts and validates JWT from Authorization: Bearer header
- Registration: email + password + display_name, email must be unique
- First user registration could be admin (or all users equal for self-hosted)

**Acceptance criteria**:
- POST /auth/register creates user, returns tokens
- POST /auth/login with valid credentials returns tokens
- POST /auth/login with invalid credentials returns 401
- Protected endpoint without token returns 401
- Protected endpoint with valid token returns data
- Expired token returns 401
- Refresh token generates new access token
- Passwords stored as bcrypt hashes (not plaintext)

**Estimated complexity**: M

---

### Plan 5.2: Data Isolation and Row-Level Security

**Description**: Ensure each user can only access their own data. Add user_id filtering to all queries and protect all API endpoints.

**Files to create**:
- `backend/app/dependencies.py` -- extend with user-scoped DB session or query filters
- `backend/app/services/*.py` -- update all service functions to accept user_id and filter queries
- `backend/app/routers/*.py` -- update all routers to inject current_user and pass user_id to services
- `backend/alembic/versions/009_rls_indexes.py` -- add indexes on user_id columns for performance
- `backend/tests/test_security/test_data_isolation.py` -- multi-user isolation tests

**Technical approach**:
- Application-level data isolation (not PostgreSQL RLS, to keep control):
  - All queries include `WHERE user_id = :current_user_id`
  - Service functions require user_id parameter
  - Router functions get user_id from `Depends(get_current_user)`
- Add composite indexes for performance:
  - `activities(user_id, activity_date DESC)`
  - `daily_fitness(user_id, date, threshold_method)`
  - `activity_metrics(activity_id)` (activity already scoped to user)
  - `thresholds(user_id, method, effective_date DESC)`
  - `health_metrics(user_id, date, metric_type)`
- Test isolation: create 2 users, add data for each, verify user A cannot access user B's data
- All existing endpoints updated with auth dependency

**Acceptance criteria**:
- User A cannot see User B's activities (GET /activities returns only own data)
- User A cannot access User B's metrics (GET /metrics/fitness scoped to current user)
- User A cannot access User B's activity streams (GET /activities/{b_id}/streams returns 403 or 404)
- All API endpoints require authentication (return 401 without token)
- Query performance not degraded (EXPLAIN shows index usage on user_id)
- Integration tests with 2+ users pass

**Estimated complexity**: L

---

### Plan 5.3: User Profile and Setup Wizard

**Description**: Build user profile management and first-run setup wizard for initial configuration.

**Files to create**:
- `backend/app/routers/users.py` -- GET /users/me (profile), PUT /users/me (update profile)
- `backend/app/schemas/user.py` -- UserProfile, UserProfileUpdate
- `backend/app/routers/setup.py` -- GET /setup/status (is setup complete?), POST /setup/init (first-time setup)
- `backend/app/schemas/setup.py` -- SetupStatus, InitialSetupRequest
- `backend/tests/test_routers/test_users.py`

**Technical approach**:
- User profile stores: display_name, email, weight_kg, date_of_birth, preferred_units (metric/imperial), timezone
- First-run setup wizard (API support for frontend in Phase 6):
  1. GET /setup/status: returns {setup_complete: false} if no users exist
  2. POST /setup/init: creates first user (admin), no auth required (only works when 0 users)
  3. Optionally accept Garmin credentials, FTP setting in same request
- After first user created, /setup/init returns 403
- Profile update requires authentication

**Acceptance criteria**:
- First request to /setup/status returns {setup_complete: false}
- POST /setup/init creates first user without requiring auth
- Second POST /setup/init returns 403
- GET /users/me returns profile data
- PUT /users/me updates profile fields
- Profile changes reflected in subsequent API calls

**Estimated complexity**: S

---

### Phase 5 Verification

```bash
# 1. Register and login
curl -X POST http://localhost:8000/auth/register -d '{"email":"rider@test.com","password":"secure123","display_name":"Test Rider"}'
# Expected: 201 with access_token

# 2. Access protected endpoint
TOKEN="<access_token from above>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/activities
# Expected: 200 with activities list

# 3. Access without token
curl http://localhost:8000/activities
# Expected: 401 Unauthorized

# 4. Data isolation (create second user)
curl -X POST http://localhost:8000/auth/register -d '{"email":"rider2@test.com","password":"secure456","display_name":"Other Rider"}'
TOKEN2="<access_token for rider2>"
curl -H "Authorization: Bearer $TOKEN2" http://localhost:8000/activities
# Expected: empty list (rider2 has no activities)

# 5. First-run setup
# (Reset database for this test)
curl http://localhost:8000/setup/status
# Expected: {"setup_complete": false}
curl -X POST http://localhost:8000/setup/init -d '{"email":"admin@test.com","password":"admin123","display_name":"Admin"}'
# Expected: 201

# 6. Run tests
cd backend && uv run pytest tests/test_routers/test_auth.py -v
cd backend && uv run pytest tests/test_security/test_data_isolation.py -v
```

---

## Phase 6: Frontend Foundation

**Goal**: User can access web interface, view activity list, and drill into basic activity details
**Requirements**: ACTV-01, ACTV-02
**Dependencies**: Phase 5

### Plan 6.1: React + Vite + TypeScript Project Setup

**Description**: Initialize the frontend project with Vite, React 18, TypeScript, and core dependencies. Set up project structure, routing, and API client.

**Files to create**:
- `frontend/package.json` -- project config with all dependencies
- `frontend/vite.config.ts` -- Vite config with proxy to backend API
- `frontend/tsconfig.json` -- TypeScript config
- `frontend/index.html` -- entry HTML
- `frontend/src/main.tsx` -- React entry point
- `frontend/src/App.tsx` -- root component with router
- `frontend/src/api/client.ts` -- Axios instance with JWT interceptor, base URL config
- `frontend/src/api/types.ts` -- TypeScript types matching backend Pydantic schemas
- `frontend/src/stores/authStore.ts` -- Zustand store for auth state (token, user, login/logout)
- `frontend/src/stores/activityStore.ts` -- Zustand store for activity list/detail
- `frontend/src/types/activity.ts` -- Activity, ActivityStream, ActivityMetrics types
- `frontend/src/types/metrics.ts` -- FitnessData, PowerZone types
- `frontend/src/components/Layout.tsx` -- app shell with navigation sidebar
- `frontend/src/components/ProtectedRoute.tsx` -- auth guard component
- `frontend/.eslintrc.cjs` -- ESLint config for React+TS

**Technical approach**:
- Create with `npm create vite@latest frontend -- --template react-ts`
- Dependencies: react, react-dom, react-router-dom, axios, zustand, recharts, react-leaflet, leaflet, date-fns
- Dev deps: @types/leaflet, eslint, prettier, @vitejs/plugin-react
- Vite proxy: `/api` -> `http://localhost:8000` for dev (avoids CORS)
- API client: Axios with interceptor that adds Authorization header from auth store
- Token refresh: interceptor catches 401, attempts refresh, retries original request
- Zustand for state management (lightweight, no boilerplate vs Redux)
- React Router v6 with routes: /login, /setup, /activities, /activities/:id, /dashboard, /settings
- Layout component: sidebar navigation (Dashboard, Activities, Settings), top bar with user info

**Acceptance criteria**:
- `npm run dev` starts Vite dev server with HMR
- App renders at http://localhost:5173
- API calls proxy to backend (no CORS errors)
- Login page displayed for unauthenticated users
- After login: redirected to activity list
- TypeScript compiles without errors
- Navigation between routes works

**Estimated complexity**: M

---

### Plan 6.2: Authentication UI

**Description**: Build login page, registration page, and first-run setup wizard in the frontend.

**Files to create**:
- `frontend/src/pages/LoginPage.tsx` -- email/password form, error handling
- `frontend/src/pages/RegisterPage.tsx` -- registration form
- `frontend/src/pages/SetupWizardPage.tsx` -- first-run setup: create account, optional Garmin/Strava connect, set FTP
- `frontend/src/components/auth/LoginForm.tsx`
- `frontend/src/components/auth/RegisterForm.tsx`
- `frontend/src/api/auth.ts` -- login(), register(), refresh(), logout() API calls

**Technical approach**:
- Login form: email + password, submit calls POST /auth/login, stores token in Zustand + localStorage
- Registration form: email + password + display_name + confirm password
- Setup wizard (shown when /setup/status returns setup_complete=false):
  1. Step 1: Create admin account (email, password, display name)
  2. Step 2: Set initial FTP (optional, can skip)
  3. Step 3: Connect Garmin (optional, save credentials)
  4. Step 4: Connect Strava (optional, OAuth redirect)
- Form validation: email format, password minimum length, password match
- Error display: inline field errors + toast notifications for API errors
- Token persistence: store in localStorage, rehydrate on app load

**Acceptance criteria**:
- Login with valid credentials -> redirected to /activities
- Login with invalid credentials -> error message displayed
- Registration creates account and logs in
- Setup wizard appears on first visit to fresh instance
- Setup wizard steps complete successfully
- Token persists across page refresh

**Estimated complexity**: M

---

### Plan 6.3: Activity List Page

**Description**: Build the activity list page with sortable table, pagination, and basic filters.

**Files to create**:
- `frontend/src/pages/ActivityListPage.tsx` -- main activity list page
- `frontend/src/components/activities/ActivityTable.tsx` -- sortable table component
- `frontend/src/components/activities/ActivityFilters.tsx` -- date range, sport type filters
- `frontend/src/components/activities/UploadButton.tsx` -- FIT file upload trigger
- `frontend/src/components/activities/UploadModal.tsx` -- drag-and-drop upload modal with progress
- `frontend/src/components/common/Pagination.tsx` -- reusable pagination component
- `frontend/src/components/common/SortHeader.tsx` -- sortable column header
- `frontend/src/api/activities.ts` -- getActivities(), uploadFit(), deleteActivity() API calls

**Technical approach**:
- Table columns: Date, Name, Duration, Distance, TSS, NP, IF, Sport Type, Source
- Sortable by: date (default DESC), duration, distance, TSS
- Pagination: 25 activities per page, load more button or page numbers
- Upload: drag-and-drop zone or file picker, supports .fit and .zip files
- Upload progress: show progress bar, then polling for processing status via GET /tasks/{id}
- After upload complete: activity appears in list (auto-refresh or manual refresh)
- Date formatting: relative for recent ("2 hours ago"), absolute for older ("Jan 15, 2026")
- Distance/duration formatting: km/mi based on user preference, HH:MM:SS duration
- Empty state: friendly message for users with no activities yet, prominent upload CTA
- Click on row -> navigate to /activities/:id

**Acceptance criteria**:
- Activity list displays with all columns populated
- Sorting by each column works (click header to toggle ASC/DESC)
- Pagination loads next page of activities
- FIT file upload via drag-and-drop works
- Upload progress indicator shown during processing
- Newly uploaded activity appears in list after processing
- Click on activity navigates to detail page
- Empty state shown for new users

**Estimated complexity**: M

---

### Plan 6.4: Activity Detail Page - Basic View

**Description**: Build the activity detail page showing metadata, summary stats, and a basic power/HR timeline chart.

**Files to create**:
- `frontend/src/pages/ActivityDetailPage.tsx` -- main detail page with tabs
- `frontend/src/components/activities/ActivityHeader.tsx` -- title, date, sport type, metadata
- `frontend/src/components/activities/ActivityStats.tsx` -- summary stats grid (duration, distance, TSS, NP, IF, avg power, max power, avg HR, max HR, elevation)
- `frontend/src/components/charts/TimelineChart.tsx` -- Recharts line chart with power and HR over time
- `frontend/src/api/streams.ts` -- getActivityStreams(), getStreamSummary() API calls
- `frontend/src/api/metrics.ts` -- getActivityMetrics() API call

**Technical approach**:
- Layout: header with metadata -> stats grid -> tabbed content area (Overview, Power, HR, Map)
- Overview tab: timeline chart + stats grid
- Timeline chart using Recharts:
  - Dual Y-axis: left for power (watts), right for heart rate (bpm)
  - `<LineChart>` with `<Line>` for power (blue) and HR (red)
  - `<Brush>` component for zoom/pan on time axis
  - Use summary endpoint (500 points) for initial load, full data on zoom
  - `<Tooltip>` shows values at cursor position
  - `<ReferenceLine>` at FTP level (dashed horizontal line)
- Responsive: full width on desktop, scrollable on mobile
- Loading state: skeleton loader while fetching stream data
- Error state: message if stream data unavailable (manual entry)

**Acceptance criteria**:
- Activity detail page loads with metadata and stats
- Timeline chart shows power and HR over time
- Brush component allows zooming into time range
- Tooltip shows values on hover
- FTP reference line visible on chart
- Manual activity shows stats only (no chart, message "No stream data")
- Page loads within 2 seconds (summary endpoint used)
- Back navigation returns to activity list

**Estimated complexity**: L

---

### Plan 6.5: Frontend Docker Integration

**Description**: Add frontend build to Docker Compose, serve built React app through Nginx alongside API proxy.

**Files to create**:
- `frontend/Dockerfile` -- multi-stage build (npm install -> npm run build -> serve via Nginx)
- `nginx/nginx.conf` -- update to serve frontend static files and proxy /api to backend
- `docker-compose.yml` -- update to include frontend build

**Technical approach**:
- Frontend Dockerfile:
  - Stage 1: Node 20 alpine, npm ci, npm run build (produces dist/)
  - Stage 2: Nginx alpine, copy dist/ to /usr/share/nginx/html
- Nginx config:
  - Location /api -> proxy_pass http://api:8000
  - Location / -> try_files $uri /index.html (SPA fallback)
  - Gzip compression for JS/CSS/HTML
  - Cache headers for static assets (1 year for hashed files)
- docker-compose.yml adds frontend service or combines into Nginx service
- Dev mode: `docker-compose.dev.yml` still runs frontend via `npm run dev` locally

**Acceptance criteria**:
- `docker compose up --build` serves full app (frontend + API)
- http://localhost shows React app
- API calls work through Nginx proxy
- SPA routing works (refresh on /activities/1 loads correctly)
- Static assets served with proper cache headers
- Build size reasonable (<2MB for initial load)

**Estimated complexity**: M

---

### Phase 6 Verification

```bash
# 1. Frontend dev server
cd frontend && npm run dev
# Visit http://localhost:5173 -- should see login page

# 2. Login flow
# Login with test credentials -> redirected to activity list

# 3. Activity list
# Expected: table with activities, sortable columns, pagination

# 4. Upload FIT file
# Drag .fit file onto upload zone -> progress -> activity appears in list

# 5. Activity detail
# Click activity -> detail page with stats and timeline chart
# Zoom chart with brush -> chart updates

# 6. Docker build
docker compose up --build
# Visit http://localhost -> full app works

# 7. Build check
cd frontend && npm run build
# Expected: no TypeScript errors, build succeeds
```

---

## Phase 7: Activity Detail Views

**Goal**: User can analyze activity with power zones, HR data, and route map
**Requirements**: ACTV-03, ACTV-04, ACTV-05, ACTV-06
**Dependencies**: Phase 6

### Plan 7.1: Power Zone Shading on Timeline (ACTV-03)

**Description**: Add 30-second power zone shading to the activity timeline chart. Each 30-second segment is colored by the Coggan power zone based on the user's configured threshold method.

**Files to create**:
- `frontend/src/components/charts/ZoneShadedTimeline.tsx` -- enhanced timeline chart with zone coloring
- `frontend/src/components/charts/ZoneLegend.tsx` -- zone color legend
- `frontend/src/utils/powerZones.ts` -- zone calculation utilities (zone boundaries from FTP, zone colors)
- `backend/app/routers/streams.py` -- extend with GET /activities/{id}/streams/zones (pre-computed zone per 30s block)
- `backend/app/schemas/stream.py` -- extend with ZoneBlock (start_time, end_time, zone, avg_power)

**Technical approach**:
- Backend: compute 30-second zones
  1. Group stream data into 30-second blocks
  2. Calculate average power per block
  3. Determine Coggan zone for each block based on user's active FTP
  4. Return list of ZoneBlock objects
- Frontend: Recharts zone shading
  - Use `<ReferenceArea>` components for each 30-second block, colored by zone
  - Zone colors (standard Coggan): Z1=gray, Z2=blue, Z3=green, Z4=yellow, Z5=orange, Z6=red, Z7=purple
  - Power line overlaid on top of zone shading
  - HR line on secondary Y-axis
  - Legend shows zone names, boundaries, and colors
- Zone boundaries change based on active threshold method (FTP value)
- Threshold method selector on chart: dropdown to switch between methods -> re-fetches zone data with ?threshold_method=

**Acceptance criteria**:
- Timeline chart shows colored 30-second blocks behind power line
- Zone colors match standard Coggan zone colors
- Zone boundaries correct relative to user's FTP
- Switching threshold method changes zone shading (different zones if FTP differs)
- Zone legend displays correctly
- Steady ride at threshold shows mostly yellow (Zone 4)
- Recovery ride shows mostly blue/gray (Zone 1-2)

**Estimated complexity**: L

---

### Plan 7.2: Power Analysis Page (ACTV-04)

**Description**: Build the power analysis detail page showing power distribution, peak efforts, variability index, and detailed power statistics.

**Files to create**:
- `frontend/src/pages/ActivityPowerPage.tsx` -- power analysis page (tab within activity detail)
- `frontend/src/components/charts/PowerDistribution.tsx` -- histogram of power values by zone
- `frontend/src/components/charts/PeakEffortsTable.tsx` -- best efforts at standard durations
- `frontend/src/components/charts/PowerScatterPlot.tsx` -- power vs HR scatter
- `backend/app/routers/metrics.py` -- extend with GET /activities/{id}/power-analysis (power stats, peak efforts, distribution)
- `backend/app/schemas/metrics.py` -- extend with PowerAnalysis, PeakEffort, PowerDistribution
- `backend/app/services/power_analysis_service.py` -- compute power distribution, peak efforts, advanced stats

**Technical approach**:
- Power distribution: histogram of seconds spent at each power level (10W bins), colored by zone
- Peak efforts table: best average power for standard durations (5s, 30s, 1min, 5min, 10min, 20min, 30min, 60min)
  - Backend computes using sliding window on stream data (same as threshold auto-detection)
- Advanced stats displayed:
  - Normalized Power, Average Power, Max Power
  - Variability Index (NP / Avg Power) -- measures how variable the ride was
  - Intensity Factor (NP / FTP)
  - TSS
  - Work (kJ) = average power * duration / 1000
  - Power-to-weight (W/kg) if weight is set
- Power vs HR scatter plot: shows aerobic decoupling (EF drift over time)
- All charts use Recharts (`<BarChart>` for distribution, `<ScatterChart>` for scatter)

**Acceptance criteria**:
- Power distribution histogram shows time in each 10W bin, colored by zone
- Peak efforts table displays correct values for all standard durations
- Advanced stats calculated correctly (TSS, VI, IF, work)
- Power vs HR scatter plot renders
- Page loads within 2 seconds
- Short ride (<5 minutes): some peak effort durations show N/A

**Estimated complexity**: L

---

### Plan 7.3: Heart Rate Analysis Page (ACTV-05)

**Description**: Build the heart rate analysis detail page with HR zones, HR distribution, and HR time-in-zone statistics.

**Files to create**:
- `frontend/src/pages/ActivityHRPage.tsx` -- HR analysis page (tab within activity detail)
- `frontend/src/components/charts/HRDistribution.tsx` -- HR histogram by zone
- `frontend/src/components/charts/HRTimeInZone.tsx` -- horizontal bar chart of time in each HR zone
- `frontend/src/utils/hrZones.ts` -- HR zone calculation (5-zone model based on max HR or LTHR)
- `backend/app/routers/metrics.py` -- extend with GET /activities/{id}/hr-analysis
- `backend/app/schemas/metrics.py` -- extend with HRAnalysis, HRZoneDistribution

**Technical approach**:
- HR zones (5-zone model based on max HR or lactate threshold HR):
  - Zone 1 (Recovery): <68% max HR
  - Zone 2 (Aerobic): 68-82% max HR
  - Zone 3 (Tempo): 83-87% max HR
  - Zone 4 (Threshold): 88-92% max HR
  - Zone 5 (VO2max/Anaerobic): >92% max HR
- User can set max HR or LTHR in settings; zones calculated from whichever is set
- HR distribution: histogram of seconds at each HR value (5 bpm bins)
- Time in zone: horizontal bar chart showing percentage of time in each zone
- HR stats: average HR, max HR, min HR, average HR for each zone
- HR drift: compare first half HR to second half HR at similar power (aerobic decoupling indicator)
- Handle rides without HR data: show message "No heart rate data available"

**Acceptance criteria**:
- HR distribution histogram displays correctly
- Time in zone bars match expected proportions
- HR zones configurable via user settings (max HR or LTHR)
- HR drift indicator calculated
- Rides without HR data show appropriate message
- Zone colors distinct from power zone colors

**Estimated complexity**: M

---

### Plan 7.4: Route Map (ACTV-06)

**Description**: Display the activity route on an interactive map using react-leaflet with OpenStreetMap tiles.

**Files to create**:
- `frontend/src/components/maps/RouteMap.tsx` -- Leaflet map with route polyline
- `frontend/src/components/maps/MapControls.tsx` -- zoom, layer toggle, full-screen
- `frontend/src/pages/ActivityMapPage.tsx` -- map page (tab within activity detail)
- `frontend/src/api/routes.ts` -- getActivityRoute() API call

**Technical approach**:
- react-leaflet `<MapContainer>` with OpenStreetMap tile layer
- Route displayed as `<Polyline>` from GeoJSON coordinates
- Map auto-fits to route bounds on load (`map.fitBounds(route.getBounds())`)
- Color options for polyline:
  - Solid color (default blue)
  - Color by power zone (gradient along route -- stretch goal)
  - Color by elevation (gradient -- stretch goal)
- Start/end markers: green circle for start, red circle for finish
- Elevation profile: small chart below map showing altitude over distance
- CyclOSM tile layer option for cycling-specific map (shows bike lanes, paths)
- Multiple tile layer options: OpenStreetMap, CyclOSM, satellite
- Handle indoor rides: no map tab visible (or show message "Indoor activity - no GPS data")

**Acceptance criteria**:
- Route map displays for outdoor activities
- Route line follows actual GPS path
- Map auto-zooms to fit route
- Start/end markers visible
- Tile layer switchable (OSM, CyclOSM)
- Indoor activities: map tab hidden or shows appropriate message
- Map is interactive (zoom, pan, click)
- Elevation profile shows below map

**Estimated complexity**: M

---

### Phase 7 Verification

```bash
# 1. Zone-shaded timeline
# Navigate to activity detail -> Overview tab
# Expected: timeline with 30-second colored blocks matching power zones

# 2. Power analysis
# Click Power tab on activity detail
# Expected: power distribution histogram, peak efforts table, advanced stats

# 3. HR analysis
# Click HR tab on activity detail
# Expected: HR distribution, time in zone bars

# 4. Route map
# Click Map tab on outdoor activity
# Expected: interactive map with route polyline, start/end markers

# 5. Indoor activity
# View indoor trainer ride
# Expected: no map tab (or "Indoor activity" message), power/HR tabs work

# 6. Threshold method switching on chart
# Change threshold method dropdown on zone-shaded timeline
# Expected: zone colors update to reflect different FTP value

# 7. Build check
cd frontend && npm run build && npm run lint
# Expected: no errors
```

---

## Phase 8: Dashboard & Charts

**Goal**: User can visualize fitness progression, critical power, and training calendar
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Dependencies**: Phase 6

### Plan 8.1: Fitness Tracker Chart (DASH-01)

**Description**: Build the Performance Management Chart (PMC) showing CTL/ATL/TSB over time with date range selection and threshold method switching.

**Files to create**:
- `frontend/src/pages/DashboardPage.tsx` -- main dashboard with fitness chart as primary view
- `frontend/src/components/charts/FitnessChart.tsx` -- CTL/ATL/TSB line chart with Recharts
- `frontend/src/components/charts/DateRangePicker.tsx` -- date range selector (preset ranges + custom)
- `frontend/src/components/charts/ThresholdMethodSelector.tsx` -- dropdown to switch threshold method
- `frontend/src/api/metrics.ts` -- extend with getFitnessData(start, end, method) API call
- `frontend/src/stores/metricsStore.ts` -- Zustand store for fitness data, date range, method selection

**Technical approach**:
- Recharts `<LineChart>` with three `<Line>` components:
  - CTL (blue, thicker): Chronic Training Load (fitness)
  - ATL (red): Acute Training Load (fatigue)
  - TSB (green, area fill): Training Stress Balance (form/freshness)
- TSB as `<Area>` with fill: green above 0 (fresh), red below 0 (fatigued)
- `<Brush>` component at bottom for zooming into time range
- Date range presets: Last 30 days, Last 90 days, Last 6 months, Last year, All time, Custom
- Threshold method selector: dropdown showing available methods (manual, 95% 20min, 90% 8min)
- Switching method re-fetches data from API (pre-cached, instant response)
- `<Tooltip>` shows CTL, ATL, TSB values and date on hover
- `<ReferenceLine>` at TSB=0 (transition between fresh and fatigued)
- Responsive: full width, minimum height 400px
- Today marker: vertical line or dot on current date

**Acceptance criteria**:
- Fitness chart displays CTL/ATL/TSB lines correctly
- Date range selection updates chart
- Brush component allows sub-range zoom
- Threshold method dropdown changes displayed values
- TSB area fill: green above zero, red below zero
- Tooltip shows all three values on hover
- Chart loads within 1 second (cached data)
- Chart renders 365+ days of data smoothly

**Estimated complexity**: L

---

### Plan 8.2: Critical Power Curve (DASH-02)

**Description**: Build the critical power curve showing the user's best power efforts across standard durations, with date range filtering and comparison overlays.

**Files to create**:
- `frontend/src/components/charts/PowerCurveChart.tsx` -- power curve line chart
- `frontend/src/pages/PowerCurvePage.tsx` -- dedicated power curve page
- `backend/app/routers/metrics.py` -- extend with GET /metrics/power-curve?start_date=&end_date=
- `backend/app/services/power_curve_service.py` -- compute mean max power for all durations
- `backend/app/schemas/metrics.py` -- extend with PowerCurveData, PowerCurvePoint
- `backend/tests/test_services/test_power_curve.py`

**Technical approach**:
- Backend: compute mean max power (MMP) curve
  - For each standard duration (1s, 2s, 5s, 10s, 30s, 1min, 2min, 5min, 10min, 20min, 30min, 60min):
    - Scan all activities in date range
    - Find best average power for that duration (sliding window)
    - Return {duration_seconds, power_watts, activity_id, date}
  - Also compute intermediate points (every 5s up to 5min, every 30s up to 30min, every 1min up to 60min) for smooth curve
  - Cache results in Redis (power curve rarely changes, invalidate on new activity import)
- Frontend: Recharts `<LineChart>` with logarithmic X-axis
  - X-axis: duration (log scale: 1s to 3600s)
  - Y-axis: power (watts)
  - Click on point: shows which activity, date, and exact power value
  - Date range filter: compare current period vs previous period (two overlaid curves)
  - Optional: overlay multiple date ranges (e.g., "this year" vs "last year")
- Reference lines at key durations (5s sprint, 1min VO2max, 5min MAP, 20min FTP proxy)

**Acceptance criteria**:
- Power curve displays with correct peak power at each duration
- Logarithmic X-axis from 1s to 60min
- Click on data point shows source activity and date
- Date range filtering works (shorter range = potentially lower values)
- Comparison overlay shows two curves with different colors
- Cache invalidated when new activity with new best effort imported
- Power curve for user with 100+ activities computes within 5 seconds

**Estimated complexity**: L

---

### Plan 8.3: Training Calendar (DASH-03, DASH-04)

**Description**: Build a monthly calendar view showing activities by day with weekly summary statistics (total TSS, duration, distance).

**Files to create**:
- `frontend/src/pages/CalendarPage.tsx` -- calendar page
- `frontend/src/components/calendar/MonthView.tsx` -- month grid with day cells
- `frontend/src/components/calendar/DayCell.tsx` -- single day showing activity indicators
- `frontend/src/components/calendar/WeeklySummary.tsx` -- weekly totals row
- `frontend/src/components/calendar/CalendarNavigation.tsx` -- month/year navigation
- `backend/app/routers/metrics.py` -- extend with GET /metrics/calendar?year=&month= (daily activity summary)
- `backend/app/schemas/metrics.py` -- extend with CalendarDay, CalendarWeek, CalendarMonth

**Technical approach**:
- Calendar grid: Monday-first by default (configurable in user settings per DASH-03)
- Each day cell shows:
  - Activity count indicator (dot or small bar)
  - Total TSS for the day (color intensity: darker = more TSS)
  - Click to expand or navigate to that day's activities
- Weekly summary row at end of each week:
  - Total TSS, total duration (HH:MM), total distance (km/mi), ride count
- Color coding: TSS intensity (light green = easy week, dark red = hard week)
- Month navigation: arrows for prev/next month, dropdown for jump to month/year
- Backend endpoint returns pre-aggregated data per day:
  - `{date, activity_count, total_tss, total_duration, total_distance, activities: [{id, name, sport_type, tss}]}`
- Use TimescaleDB `time_bucket('1 day', activity_date)` for efficient aggregation

**Acceptance criteria**:
- Calendar displays correct month with Monday-first layout
- Days with activities show indicators and TSS
- Weekly summary row shows correct totals
- Month navigation works
- Click on day shows activities for that day
- Empty days render correctly
- Configurable start day (Monday vs Sunday) from user settings
- Current day highlighted

**Estimated complexity**: M

---

### Plan 8.4: Totals Page with Charts (DASH-05)

**Description**: Build the totals page showing aggregated training statistics with weekly, monthly, and yearly trend charts.

**Files to create**:
- `frontend/src/pages/TotalsPage.tsx` -- totals page with period selector and charts
- `frontend/src/components/charts/TotalsBarChart.tsx` -- stacked bar chart for TSS/duration/distance over time
- `frontend/src/components/charts/TotalsSummaryCards.tsx` -- summary stat cards (total rides, distance, time, TSS)
- `frontend/src/components/charts/PeriodSelector.tsx` -- weekly/monthly/yearly toggle
- `backend/app/routers/metrics.py` -- extend with GET /metrics/totals?period=weekly&start_date=&end_date=
- `backend/app/services/totals_service.py` -- aggregate totals by period
- `backend/app/schemas/metrics.py` -- extend with TotalsPeriod, TotalsResponse

**Technical approach**:
- Period aggregation: weekly, monthly, yearly
- Backend uses `time_bucket` for efficient aggregation:
  - Weekly: `time_bucket('1 week', activity_date)`
  - Monthly: `time_bucket('1 month', activity_date)`
  - Yearly: `time_bucket('1 year', activity_date)`
- Returns: {period_start, activity_count, total_tss, total_duration_hours, total_distance_km, total_elevation_m}
- Frontend: Recharts `<BarChart>` with grouped bars
  - Bars for: TSS, duration, distance (different Y-axes)
  - Toggle between metrics (show TSS bars, or duration bars, or distance bars)
  - Or stacked: TSS + duration combined view
- Summary cards at top: Year-to-date totals (rides, distance, time, TSS, elevation)
- Comparison: show current year vs previous year (optional overlay)
- Year-over-year table: compare months across years

**Acceptance criteria**:
- Weekly totals bar chart displays correctly
- Monthly totals bar chart displays correctly
- Yearly totals display correctly
- Summary cards show accurate year-to-date totals
- Period selector switches between weekly/monthly/yearly views
- Chart responds to date range changes
- Correct handling of partial weeks/months at boundaries

**Estimated complexity**: M

---

### Plan 8.5: Dashboard Layout and Navigation

**Description**: Finalize the dashboard page layout combining the fitness chart as the main view with quick-access widgets for recent activities, upcoming milestones, and training summary.

**Files to create**:
- `frontend/src/pages/DashboardPage.tsx` -- finalize dashboard layout
- `frontend/src/components/dashboard/RecentActivities.tsx` -- last 5 activities widget
- `frontend/src/components/dashboard/TrainingSummary.tsx` -- this week's stats widget
- `frontend/src/components/dashboard/FitnessSnapshot.tsx` -- current CTL/ATL/TSB values
- `frontend/src/components/Layout.tsx` -- update navigation with all pages

**Technical approach**:
- Dashboard layout:
  - Top: FitnessSnapshot (current CTL, ATL, TSB values with trend arrows)
  - Middle: FitnessChart (main PMC chart, takes most space)
  - Bottom-left: RecentActivities (last 5 rides, clickable)
  - Bottom-right: TrainingSummary (this week: rides, TSS, hours, distance)
- Navigation sidebar (update):
  - Dashboard (home icon)
  - Activities (list icon)
  - Calendar (calendar icon)
  - Power Curve (chart icon)
  - Totals (bar chart icon)
  - Settings (gear icon)
- Responsive layout: widgets stack vertically on mobile
- Dashboard data loaded with single API call or parallel requests on mount

**Acceptance criteria**:
- Dashboard shows fitness snapshot with current values
- Fitness chart renders as primary view
- Recent activities widget shows last 5 rides
- Training summary shows this week's totals
- Navigation provides access to all pages
- Responsive: works on desktop and tablet
- Page loads within 2 seconds total

**Estimated complexity**: M

---

### Phase 8 Verification

```bash
# 1. Fitness chart
# Navigate to Dashboard
# Expected: CTL/ATL/TSB chart with correct data, date range picker, method selector

# 2. Critical power curve
# Navigate to Power Curve page
# Expected: curve from 1s to 60min, click on point shows source activity

# 3. Training calendar
# Navigate to Calendar
# Expected: monthly view with activity indicators, weekly summaries, correct TSS totals

# 4. Totals page
# Navigate to Totals
# Expected: bar charts for weekly/monthly/yearly, summary cards with YTD totals

# 5. Dashboard widgets
# Visit Dashboard
# Expected: fitness snapshot, recent activities, weekly summary all populated

# 6. Method switching
# Change threshold method on fitness chart
# Expected: values update instantly (pre-cached data)

# 7. Full build and deploy
docker compose up --build
# Visit http://localhost -> login -> dashboard -> all features working

# 8. Performance check
# Fitness chart with 1 year of data: loads within 1 second
# Power curve with 500+ activities: computes within 5 seconds
# Calendar month view: loads within 500ms
```

---

## Cross-Phase Concerns

### Testing Strategy

| Phase | Test Types | Key Tests |
|-------|-----------|-----------|
| 1 | Unit (FIT parser), Integration (upload API), E2E (upload flow) | FIT device matrix, duplicate detection, stream storage |
| 2 | Unit (Coggan formulas), Integration (computation pipeline) | NP edge cases, TSS accuracy, CTL/ATL/TSB math |
| 3 | Integration (OAuth flow), Unit (rate limiter) | Token refresh, webhook handling, duplicate sync |
| 4 | Unit (threshold estimation), Integration (multi-method) | Best effort detection, instant switching |
| 5 | Integration (auth), Security (data isolation) | JWT lifecycle, multi-user isolation |
| 6 | Component (React), E2E (login -> upload -> view) | Activity list, upload flow, navigation |
| 7 | Component (charts), Visual (zone colors) | Zone shading accuracy, map rendering |
| 8 | Component (charts), Integration (aggregation) | Fitness chart data, calendar correctness |

### Database Migration Sequence

| Migration | Phase | Description |
|-----------|-------|-------------|
| 001_initial_schema | 1.2 | users (with seed user), activities, activity_streams (hypertable), activity_laps, health_metrics |
| 002_import_batch | 1.7 | import_batch table |
| 003_integrations | 1.8 | integrations table (Garmin, Strava credentials) |
| 004_user_settings | 2.2 | user_settings table (FTP, preferences) |
| 005_activity_metrics | 2.3 | activity_metrics table |
| 006_daily_fitness | 2.4 | daily_fitness table |
| 007_strava_integration | 3.1 | Strava token fields on integrations |
| 008_threshold_management | 4.1 | thresholds table with multi-method support |
| 009_rls_indexes | 5.2 | user_id composite indexes for data isolation |

### Precision Guarantee Chain

All power calculations maintain precision from storage through computation to display:
1. FIT parser extracts integer watts -> stored as INT in activity_streams
2. NP calculation uses NumPy float64 for performance (sub-0.01W worst-case error); final result rounded to 1 decimal place and stored as NUMERIC in PostgreSQL
3. TSS/IF stored as NUMERIC in activity_metrics
4. CTL/ATL/TSB stored as NUMERIC in daily_fitness
5. API returns string-formatted decimals (not IEEE 754 floats)
6. Frontend displays with fixed precision (1 decimal for TSS, 2 for IF)

### Continuous Aggregates Decision

TimescaleDB continuous aggregates (e.g., `daily_totals`, `weekly_fitness`, `power_curve_cache`) were evaluated as an architectural pattern for materializing aggregate queries. For this self-hosted, low-user-count platform, the decision was to defer continuous aggregates in favor of pre-computed regular tables (`daily_fitness`) combined with Redis caching. Rationale: (1) Pre-computed tables are simpler to reason about and debug. (2) Redis cache provides sub-100ms response times for dashboard queries. (3) The maintenance overhead of continuous aggregates (refresh policies, cagg-specific migration constraints) is not justified at this scale. If query times exceed targets during Phase 8 verification, continuous aggregates can be added as a performance optimization without schema changes to the application layer.

---

*Plans created: 2026-02-10*
*Phases covered: 1-8 (42 plans total)*
*Phases deferred: 9-11 (Xert algorithms, Season Planning)*
