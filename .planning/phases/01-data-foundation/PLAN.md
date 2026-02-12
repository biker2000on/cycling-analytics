# Phase 1: Data Foundation

**Goal**: User can import FIT files and store ride data with numerical precision in TimescaleDB hypertables
**Requirements**: DATA-01, DATA-03, DATA-04, DATA-05, INFR-02, INFR-03, INFR-04
**Dependencies**: None (first phase)

> **Key constraint**: PostgreSQL + TimescaleDB + PostGIS runs on the user's NAS, NOT in Docker. Docker Compose runs the FastAPI app, Celery worker, and Redis only. Dev environment runs Python locally with uv; Docker is only for services (Redis).

## Plan 1.1: Project Scaffolding and Backend Skeleton

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

## Plan 1.2: Database Setup and Alembic Migrations

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

## Plan 1.3: Docker Compose for Development and Deployment

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

## Plan 1.4: Celery Worker Setup and Task Infrastructure

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

## Plan 1.5: FIT File Parser and Import Pipeline

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

## Plan 1.6: Activity Upload API and Storage Pipeline

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

## Plan 1.7: Zip Archive and Bulk Import Support

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

## Plan 1.8: Garmin Connect Automated Sync

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

## Plan 1.9: Manual Activity Entry and CSV Import

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

## Plan 1.10: Activity Streams API and Data Access Layer

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

## Phase 1 Verification

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
