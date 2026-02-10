# Architecture Research

**Domain:** Cycling Analytics Platform
**Researched:** 2026-02-10
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SPA)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Dashboard   │  │   Activity   │  │    Route     │              │
│  │   Charts     │  │   Details    │  │     Map      │              │
│  │  (Recharts)  │  │  (Power/HR)  │  │  (Leaflet)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│         └─────────────────┴─────────────────┘                        │
│                           │                                          │
│                    REST API (JSON)                                   │
├───────────────────────────┴─────────────────────────────────────────┤
│                       FASTAPI BACKEND                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │   Auth   │  │Activities│  │ Metrics  │  │  Routes  │           │
│  │  Router  │  │  Router  │  │  Router  │  │  Router  │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │             │              │             │                  │
├───────┴─────────────┴──────────────┴─────────────┴─────────────────┤
│                      SERVICE LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Import     │  │   Compute    │  │   External   │             │
│  │   Service    │  │   Service    │  │     API      │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                       │
├─────────┴─────────────────┴─────────────────┴───────────────────────┤
│                   BACKGROUND WORKERS (Celery)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  FIT Parser  │  │    Strava    │  │    Metric    │             │
│  │   Worker     │  │    Sync      │  │   Computer   │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                       │
├─────────┴─────────────────┴─────────────────┴───────────────────────┤
│                         DATA LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         PostgreSQL + TimescaleDB + PostGIS               │       │
│  ├──────────────────────────────────────────────────────────┤       │
│  │  Regular Tables:                                          │       │
│  │  • users, activities, thresholds, user_preferences       │       │
│  ├──────────────────────────────────────────────────────────┤       │
│  │  Hypertables (time-partitioned):                          │       │
│  │  • activity_streams (second-by-second power/HR/cadence)  │       │
│  │  • activity_laps                                          │       │
│  ├──────────────────────────────────────────────────────────┤       │
│  │  Continuous Aggregates:                                   │       │
│  │  • daily_totals, weekly_fitness, monthly_stats           │       │
│  │  • power_curve_cache                                      │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    Redis Cache                            │       │
│  │  • Computed CTL/ATL/TSB values                            │       │
│  │  • Critical power curves                                  │       │
│  │  • Session tokens                                         │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Frontend SPA** | User interface, data visualization, route display | React/Svelte + Recharts + Leaflet |
| **FastAPI Backend** | REST API, request validation, auth, routing | FastAPI with APIRouter modules |
| **Service Layer** | Business logic, data transformations, external integrations | Python service classes |
| **Background Workers** | Async processing: file parsing, API syncs, metric computation | Celery with Redis broker |
| **PostgreSQL** | Persistent storage: users, activities, metadata | Standard relational tables |
| **TimescaleDB Hypertables** | High-frequency time-series data (second-by-second streams) | Automatically partitioned chunks |
| **Continuous Aggregates** | Pre-computed rollups (daily/weekly totals) | TimescaleDB materialized views |
| **PostGIS** | Geospatial route data, coordinate storage | PostgreSQL extension |
| **Redis** | Fast cache for computed metrics, session storage | In-memory key-value store |

## Recommended Project Structure

```
cycling-analytics/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app initialization
│   │   ├── config.py               # Environment config, settings
│   │   ├── database.py             # SQLAlchemy setup, session management
│   │   │
│   │   ├── routers/                # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # Login, registration, JWT
│   │   │   ├── activities.py       # Activity CRUD, upload
│   │   │   ├── metrics.py          # Fitness metrics (CTL/ATL/TSB)
│   │   │   ├── streams.py          # Second-by-second data
│   │   │   ├── routes.py           # Geographic routes
│   │   │   └── integrations.py     # Strava/Garmin OAuth
│   │   │
│   │   ├── services/               # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── import_service.py   # FIT file parsing orchestration
│   │   │   ├── compute_service.py  # Xert algorithms, Coggan model
│   │   │   ├── strava_service.py   # Strava API client
│   │   │   ├── cache_service.py    # Redis cache management
│   │   │   └── threshold_service.py # Multiple threshold methods
│   │   │
│   │   ├── workers/                # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py       # Celery initialization
│   │   │   ├── fit_parser.py       # Parse FIT files async
│   │   │   ├── strava_sync.py      # Fetch from Strava async
│   │   │   └── metric_computer.py  # Background metric computation
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── activity.py
│   │   │   ├── activity_stream.py  # Hypertable model
│   │   │   ├── threshold.py
│   │   │   └── route.py            # PostGIS geometry
│   │   │
│   │   ├── schemas/                # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── activity.py
│   │   │   └── metrics.py
│   │   │
│   │   ├── dependencies.py         # Shared dependencies (DB session, auth)
│   │   ├── security.py             # JWT, password hashing
│   │   └── utils/                  # Helpers
│   │       ├── fit_parser.py       # python-fitparse wrapper
│   │       ├── xert_algorithms.py  # Reverse-engineered algorithms
│   │       └── coggan_model.py     # CTL/ATL/TSB calculations
│   │
│   ├── tests/
│   │   ├── test_routers/
│   │   ├── test_services/
│   │   └── test_workers/
│   │
│   ├── alembic/                    # Database migrations
│   │   └── versions/
│   │
│   ├── pyproject.toml              # uv project config
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx       # Fitness chart dashboard
│   │   │   ├── ActivityDetail.tsx  # Power/HR zones, intervals
│   │   │   ├── RouteMap.tsx        # Leaflet map component
│   │   │   └── Charts/
│   │   │       ├── FitnessChart.tsx   # CTL/ATL/TSB
│   │   │       ├── PowerCurve.tsx     # Critical power
│   │   │       └── TotalsChart.tsx    # Weekly/monthly totals
│   │   │
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ActivityListPage.tsx
│   │   │   └── ActivityDetailPage.tsx
│   │   │
│   │   ├── api/
│   │   │   └── client.ts           # Axios/fetch wrapper with auth
│   │   │
│   │   ├── stores/                 # State management (Zustand/Redux)
│   │   │   ├── authStore.ts
│   │   │   ├── activityStore.ts
│   │   │   └── metricsStore.ts
│   │   │
│   │   └── types/                  # TypeScript types
│   │       ├── activity.ts
│   │       └── metrics.ts
│   │
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml              # Multi-service orchestration
├── .env.example
└── README.md
```

### Structure Rationale

- **Backend/Frontend Separation:** Clean separation enables independent scaling and deployment. Frontend can be served via CDN, backend scales horizontally.
- **Router Modularity:** Each router module (auth, activities, metrics) is self-contained with its own endpoints, reducing merge conflicts in teams.
- **Service Layer Isolation:** Business logic lives in services, not routers. This enables unit testing without HTTP overhead and reuse across routers/workers.
- **Worker Separation:** Celery workers run in separate processes, preventing long-running tasks (FIT parsing, Strava sync) from blocking the API.
- **Model/Schema Split:** SQLAlchemy models (DB) vs Pydantic schemas (API) separation follows FastAPI best practices, enabling validation and serialization layers.

## Architectural Patterns

### Pattern 1: Modular Monolith (Recommended)

**What:** Single deployable backend with clear internal module boundaries. Frontend as separate SPA.

**When to use:**
- MVP and early growth stages (< 100K users)
- Small to medium teams (1-5 backend developers)
- When simplicity and fast iteration are priorities

**Trade-offs:**
- ✅ **Pros:** Simple deployment, single database transaction boundary, easier debugging, lower operational overhead
- ❌ **Cons:** Cannot scale components independently, all services share same failure domain

**Build order implications:** Build all components in one repository, deploy as single Docker service. Revisit if specific bottlenecks emerge (e.g., metric computation needs dedicated scaling).

**Example:**
```python
# Backend deployed as single FastAPI app
# docker-compose.yml
services:
  api:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://...

  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker
    depends_on: [api, redis]
```

### Pattern 2: Database-Centric Caching Strategy

**What:** Use TimescaleDB continuous aggregates for time-based rollups, Redis for frequently accessed computed metrics.

**When to use:**
- When same data queried repeatedly (dashboard fitness charts)
- When computation is expensive (Xert algorithms on full ride history)
- When staleness tolerance is acceptable (5-minute old CTL is fine)

**Trade-offs:**
- ✅ **Pros:** Massive query speedup (10-100x), reduced database load, continuous aggregates auto-update
- ❌ **Cons:** Cache invalidation complexity, additional Redis infrastructure, potential stale data

**Example:**
```sql
-- TimescaleDB continuous aggregate for daily fitness totals
CREATE MATERIALIZED VIEW daily_fitness
WITH (timescaledb.continuous) AS
SELECT
  user_id,
  time_bucket('1 day', activity_date) AS day,
  SUM(tss) as daily_tss,
  AVG(intensity_factor) as avg_if
FROM activities
GROUP BY user_id, day;

-- Refresh policy: auto-update every hour
SELECT add_continuous_aggregate_policy('daily_fitness',
  start_offset => INTERVAL '3 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
```

```python
# Redis cache for expensive computed metrics
async def get_fitness_chart(user_id: int) -> FitnessData:
    cache_key = f"fitness:{user_id}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return FitnessData.parse_raw(cached)

    # Compute from continuous aggregate + recent data
    data = await compute_ctl_atl_tsb(user_id)

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, data.json())
    return data
```

### Pattern 3: Hybrid Time-Series Schema Design

**What:** Use TimescaleDB hypertables for second-by-second data, regular tables for metadata, continuous aggregates for rollups.

**When to use:** Always for this domain. Cycling activities generate massive time-series data (1 second granularity for hours).

**Trade-offs:**
- ✅ **Pros:** Query performance on time-ranges (10-100x faster), automatic partitioning, compression (90%+ space savings)
- ❌ **Cons:** Slightly more complex migrations, must understand chunk intervals

**Decision matrix:**

| Data Type | Table Type | Rationale |
|-----------|-----------|-----------|
| Second-by-second power/HR/cadence | **Hypertable** | High-volume time-series (3600+ rows/hour), time-range queries |
| Activity metadata (date, name, distance) | **Regular table** | Low-volume, accessed by activity_id not time |
| Daily/weekly fitness totals | **Continuous aggregate** | Pre-computed rollups from hypertables |
| User profiles, thresholds | **Regular table** | Not time-series, updated infrequently |
| Routes (geographic paths) | **Regular table + PostGIS** | Geospatial data, indexed by geometry |

**Example:**
```sql
-- Regular table for activity metadata
CREATE TABLE activities (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL,
  activity_date TIMESTAMPTZ NOT NULL,
  name TEXT,
  distance_km NUMERIC,
  duration_seconds INT,
  tss NUMERIC,  -- Cached computed metric
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Hypertable for second-by-second streams
CREATE TABLE activity_streams (
  activity_id INT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  power_watts INT,
  heart_rate INT,
  cadence INT,
  altitude_m NUMERIC,
  position GEOGRAPHY(POINT, 4326),  -- PostGIS
  FOREIGN KEY (activity_id) REFERENCES activities(id)
);

-- Convert to hypertable (time-partitioned)
SELECT create_hypertable('activity_streams', 'timestamp',
  chunk_time_interval => INTERVAL '1 week',
  if_not_exists => TRUE
);

-- Enable compression for chunks older than 7 days
ALTER TABLE activity_streams SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'activity_id'
);

SELECT add_compression_policy('activity_streams', INTERVAL '7 days');
```

### Pattern 4: Background Job Processing with Celery

**What:** Offload slow operations (FIT parsing, Strava API calls, metric computation) to async workers.

**When to use:**
- Any operation taking > 1 second
- External API calls (rate-limited)
- CPU-intensive computations (Xert algorithms on full power file)

**Trade-offs:**
- ✅ **Pros:** Fast API responses, retry logic, horizontal scaling of workers
- ❌ **Cons:** Added complexity, need message broker (Redis), eventual consistency

**Example:**
```python
# Router delegates to background worker
@router.post("/upload-fit")
async def upload_fit_file(
    file: UploadFile,
    user: User = Depends(get_current_user)
):
    # Store file temporarily
    file_path = await save_upload(file)

    # Queue background processing
    task = parse_fit_file.delay(user.id, file_path)

    return {"task_id": task.id, "status": "processing"}

# Celery worker
@celery_app.task(bind=True, max_retries=3)
def parse_fit_file(self, user_id: int, file_path: str):
    try:
        # Parse FIT file (python-fitparse)
        activity, streams = parse_fit(file_path)

        # Store in database
        save_activity(user_id, activity, streams)

        # Trigger metric computation
        compute_metrics.delay(activity.id)

        return {"status": "success", "activity_id": activity.id}
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Pattern 5: Multi-Method Threshold Management

**What:** Store multiple threshold values per user (e.g., lab-tested FTP vs auto-detected vs manually set), compute metrics for all methods, let users switch views.

**When to use:** When accuracy is critical but uncertainty exists. Different athletes trust different methods.

**Trade-offs:**
- ✅ **Pros:** Flexibility, users can compare methods, no data loss when changing methods
- ❌ **Cons:** Increased storage, must pre-compute metrics for all methods or compute on-demand

**Example:**
```sql
CREATE TABLE thresholds (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL,
  method VARCHAR(50) NOT NULL,  -- 'manual', 'auto_20min', 'lab_test', 'ramp_test'
  effective_date DATE NOT NULL,
  ftp_watts INT NOT NULL,
  lthr_bpm INT,
  is_active BOOLEAN DEFAULT TRUE,
  UNIQUE(user_id, method, effective_date)
);

-- Metrics cached per threshold method
CREATE TABLE fitness_metrics (
  user_id INT NOT NULL,
  date DATE NOT NULL,
  threshold_method VARCHAR(50) NOT NULL,
  ctl NUMERIC,  -- Chronic Training Load
  atl NUMERIC,  -- Acute Training Load
  tsb NUMERIC,  -- Training Stress Balance
  PRIMARY KEY (user_id, date, threshold_method)
);
```

**API allows switching:**
```python
@router.get("/metrics/fitness")
async def get_fitness_metrics(
    threshold_method: str = Query("auto_20min"),
    user: User = Depends(get_current_user)
):
    # Fetch cached metrics for this threshold method
    return await get_fitness_data(user.id, threshold_method)
```

## Data Flow

### Flow 1: FIT File Upload → Storage → Metrics

```
User uploads FIT file
    ↓
FastAPI /upload-fit endpoint
    ↓
Validation (file type, size)
    ↓
Store temporary file
    ↓
Queue Celery task: parse_fit_file.delay()
    ↓ (async, return task_id immediately)
─────────────────────────────────────────────
Celery Worker: parse_fit_file
    ↓
Parse FIT file (python-fitparse)
    ↓
Extract: activity metadata + second-by-second streams
    ↓
DB Transaction:
  - INSERT INTO activities (metadata)
  - BULK INSERT INTO activity_streams (hypertable)
  - INSERT route coordinates (PostGIS)
    ↓
Queue next task: compute_metrics.delay(activity_id)
─────────────────────────────────────────────
Celery Worker: compute_metrics
    ↓
Fetch all activities for user
    ↓
Apply Xert algorithms (XSS, MPA, etc.)
    ↓
Apply Coggan model (CTL/ATL/TSB)
    ↓
Cache results in Redis (5 min TTL)
    ↓
Update activities table (tss, intensity_factor)
    ↓
Send webhook/notification: "Activity processed"
```

### Flow 2: Strava Webhook → Sync Activity

```
Strava webhook POST /webhooks/strava
    ↓
Verify webhook signature
    ↓
Parse event: { aspect_type: "create", object_id: 12345 }
    ↓
Queue Celery task: sync_strava_activity.delay(object_id)
    ↓ (return 200 OK immediately)
─────────────────────────────────────────────
Celery Worker: sync_strava_activity
    ↓
Fetch activity from Strava API
    ↓
Check if already synced (avoid duplicates)
    ↓
Fetch detailed streams (power, HR, GPS)
    ↓
DB Transaction:
  - INSERT INTO activities
  - BULK INSERT INTO activity_streams
    ↓
Queue: compute_metrics.delay(activity_id)
```

### Flow 3: Dashboard Load → Fitness Chart

```
Frontend requests: GET /metrics/fitness?threshold_method=auto_20min
    ↓
FastAPI router: get_fitness_metrics
    ↓
Dependency injection: get_current_user() (verify JWT)
    ↓
Service layer: cache_service.get_fitness_data()
    ↓
Check Redis cache: fitness:{user_id}:{threshold_method}
    │
    ├─ Cache HIT → Return cached data (5ms response)
    │
    └─ Cache MISS:
        ↓
      Query TimescaleDB continuous aggregate (daily_fitness)
        ↓
      Fetch recent raw data (last 7 days, not yet in aggregate)
        ↓
      Compute CTL/ATL/TSB using Coggan formulas
        ↓
      Store in Redis (TTL 5 minutes)
        ↓
      Return data
    ↓
Frontend: Render Recharts line chart (CTL/ATL/TSB curves)
```

### Flow 4: Threshold Change → Recalculate Metrics

```
User updates FTP: POST /thresholds { method: "manual", ftp_watts: 280 }
    ↓
FastAPI router: update_threshold
    ↓
DB: INSERT new threshold row (effective_date = today)
    ↓
Invalidate Redis cache: DEL fitness:{user_id}:*
    ↓
Queue Celery task: recalculate_all_metrics.delay(user_id, method="manual")
    ↓
─────────────────────────────────────────────
Celery Worker: recalculate_all_metrics
    ↓
Fetch all activities for user
    ↓
Recompute TSS for each activity (using new FTP)
    ↓
Recompute CTL/ATL/TSB time series (Coggan model)
    ↓
UPDATE fitness_metrics table (for method="manual")
    ↓
Cache results in Redis
    ↓
Send notification: "Metrics recalculated"
```

## Build Order and Dependencies

Recommended phase structure based on dependencies:

### Phase 1: Core Infrastructure
**Dependencies:** None
**What to build:**
- Docker Compose setup (PostgreSQL + TimescaleDB + Redis)
- Database schema (users, activities tables)
- Basic FastAPI app structure
- Health check endpoints

**Why first:** Foundation for all other work. Can't develop without database.

### Phase 2: Authentication & User Management
**Dependencies:** Phase 1
**What to build:**
- User registration/login (JWT)
- Password hashing (bcrypt)
- Protected route dependencies
- Multi-user database isolation

**Why second:** Required before any personalized features. Establishes security model.

### Phase 3: FIT File Import & Storage
**Dependencies:** Phase 1, Phase 2
**What to build:**
- File upload endpoint
- python-fitparse integration
- Celery worker setup (Redis broker)
- activity_streams hypertable
- Basic activity CRUD endpoints

**Why third:** Core value proposition. Users need to get data in before anything else matters.

### Phase 4: Strava Integration
**Dependencies:** Phase 2, Phase 3
**What to build:**
- OAuth2 flow for Strava
- Strava API sync service
- Webhook subscription & handling
- Duplicate detection logic

**Why fourth:** Expands data sources. Builds on Phase 3's storage patterns.

### Phase 5: Basic Metric Computation
**Dependencies:** Phase 3
**What to build:**
- Xert algorithm implementation (XSS calculation)
- Coggan model (CTL/ATL/TSB)
- Threshold management (single method: manual)
- Background metric computation worker

**Why fifth:** Transforms raw data into insights. First user-visible analytics.

### Phase 6: Frontend Dashboard
**Dependencies:** Phase 2, Phase 5
**What to build:**
- React/Svelte SPA setup
- Authentication flow (login UI)
- Dashboard with fitness chart (Recharts: CTL/ATL/TSB)
- Activity list view

**Why sixth:** First complete user experience. Can demo end-to-end flow.

### Phase 7: Route Visualization
**Dependencies:** Phase 3, Phase 6
**What to build:**
- PostGIS route storage
- Leaflet map component
- Route detail page
- OpenStreetMap tile configuration

**Why seventh:** Enhances activity detail view. Geospatial feature, less critical than metrics.

### Phase 8: Advanced Analytics
**Dependencies:** Phase 5
**What to build:**
- Power curve (critical power)
- Multiple threshold methods
- Continuous aggregates (daily/weekly rollups)
- Redis caching layer

**Why eighth:** Optimization and expansion. Core features work without this.

### Phase 9: Activity Detail Views
**Dependencies:** Phase 6, Phase 7
**What to build:**
- Power zone charts
- HR analysis
- Interval detection
- Lap summaries

**Why ninth:** Rich detail view. Builds on all previous analytics work.

### Phase 10: Season Planning
**Dependencies:** Phase 5, Phase 8
**What to build:**
- Goal setting UI
- CTL progression modeling
- Training block creation

**Why last:** Advanced feature. Requires solid analytics foundation.

## Database Schema Strategy

### When to Use Hypertables

**Use hypertables for:**
- `activity_streams` — Second-by-second power/HR/cadence/GPS (high-volume, time-range queries)
- `activity_laps` — Lap splits over time (if storing historical lap data per activity)

**Why:**
- Queries like "get all power data for activity X" are time-range queries (activity start → end)
- Automatic partitioning by time (chunk_interval = 1 week) keeps query scans small
- Compression saves 90%+ storage after 7 days

**Chunk interval guidance:**
- 1 week chunks for activity_streams (balance between too many chunks and too large chunks)
- Each chunk ~500MB uncompressed is optimal

### When to Use Regular Tables

**Use regular tables for:**
- `users` — User profiles (not time-series, accessed by user_id)
- `activities` — Activity metadata (accessed by activity_id, not time-scanned)
- `thresholds` — User threshold history (low-volume, complex joins)
- `routes` — Geographic paths with PostGIS (indexed by geometry, not time)

**Why:**
- Not time-series data (no timestamp-based partitioning benefit)
- Accessed by primary key or foreign key, not time ranges
- Complex joins work better on regular tables

### When to Use Continuous Aggregates

**Use continuous aggregates for:**
- `daily_totals` — SUM(distance), SUM(tss) per day per user
- `weekly_fitness` — CTL/ATL/TSB per week (pre-computed from daily)
- `monthly_stats` — Aggregate totals for calendar views
- `power_curve_cache` — Pre-computed max power for durations 1s-60min

**Why:**
- Dashboard queries hit these repeatedly ("show me last 90 days")
- Expensive aggregations (CTL requires exponential moving average over all history)
- Auto-refresh keeps data fresh without manual triggers

**Example:**
```sql
-- Continuous aggregate: daily TSS totals
CREATE MATERIALIZED VIEW daily_tss
WITH (timescaledb.continuous) AS
SELECT
  user_id,
  time_bucket('1 day', activity_date) AS day,
  SUM(tss) as total_tss,
  COUNT(*) as activity_count
FROM activities
GROUP BY user_id, day;

-- Refresh every hour for last 3 days (real-time-ish)
SELECT add_continuous_aggregate_policy('daily_tss',
  start_offset => INTERVAL '3 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
```

### Compression Strategy

```sql
-- Compress activity_streams older than 7 days
ALTER TABLE activity_streams SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'activity_id',  -- Group by activity for efficient decompression
  timescaledb.compress_orderby = 'timestamp DESC'  -- Recent data first
);

SELECT add_compression_policy('activity_streams', INTERVAL '7 days');
```

**Expected compression ratios:**
- Power/HR/cadence data: 10-20x compression (integers compress well)
- GPS coordinates: 5-10x compression

## Background Job Processing Approach

### When to Use Celery vs Inline Processing

| Operation | Processing | Reason |
|-----------|-----------|--------|
| FIT file parsing | **Celery** | Takes 2-10 seconds, CPU-intensive |
| Strava API fetch | **Celery** | External API, rate-limited, can timeout |
| Metric computation (full history) | **Celery** | Expensive, can take 30+ seconds for 1000 activities |
| Single activity TSS calculation | **Inline** | Fast (<100ms), needed for immediate response |
| Dashboard query (cached) | **Inline** | Cache hit is <10ms |
| Dashboard query (uncached) | **Inline with timeout** | Acceptable latency (<2s), user waiting |

### Celery Architecture

```python
# workers/celery_app.py
from celery import Celery

celery_app = Celery(
    "cycling-analytics",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=540,  # 9 minute soft limit
)
```

### Task Priority Queues

```python
# High-priority: user-facing tasks
@celery_app.task(queue="high_priority", max_retries=3)
def parse_fit_file_uploaded_now(user_id, file_path):
    # User waiting for this to complete
    pass

# Low-priority: background sync
@celery_app.task(queue="low_priority", max_retries=5)
def sync_strava_webhook(activity_id):
    # Can take longer, user not waiting
    pass
```

**Docker Compose workers:**
```yaml
services:
  worker-high:
    build: ./backend
    command: celery -A app.workers.celery_app worker -Q high_priority -c 4

  worker-low:
    build: ./backend
    command: celery -A app.workers.celery_app worker -Q low_priority -c 2
```

### Error Handling & Retries

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_strava_activity(self, strava_activity_id):
    try:
        response = strava_api.get_activity(strava_activity_id)
        return response
    except StravaRateLimitError as exc:
        # Retry after rate limit window
        raise self.retry(exc=exc, countdown=exc.retry_after)
    except StravaNotFoundError:
        # Don't retry, activity deleted
        logger.error(f"Activity {strava_activity_id} not found")
        return None
    except Exception as exc:
        # Exponential backoff for other errors
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

## API Design: REST vs GraphQL

**Recommendation:** Use REST for MVP and early phases.

### Why REST for This Project

**Advantages:**
- ✅ Simpler implementation (FastAPI's strength)
- ✅ Clear caching semantics (HTTP cache headers)
- ✅ Well-defined endpoints match domain (GET /activities, GET /metrics/fitness)
- ✅ TimescaleDB continuous aggregates align with REST endpoints (pre-aggregated data)
- ✅ Easier to optimize specific queries (index per endpoint)

**When GraphQL makes sense:**
- Multiple related entities needed in one request (activity + user + thresholds + streams)
- Mobile app needs precise field selection to reduce payload
- Many frontend variations (web, mobile, watch faces) with different data needs

**Hybrid approach for later:**
- REST for CRUD and simple analytics (GET /activities, POST /upload-fit)
- GraphQL for complex dashboard queries (activity list + metrics + totals in one request)

### REST Endpoint Design

```
Auth:
  POST   /auth/register
  POST   /auth/login
  POST   /auth/refresh

Activities:
  GET    /activities                    # List with pagination
  POST   /activities/upload-fit         # Upload FIT file
  GET    /activities/{id}               # Metadata only
  GET    /activities/{id}/streams       # Second-by-second data (large payload)
  GET    /activities/{id}/route         # GeoJSON route
  DELETE /activities/{id}

Metrics:
  GET    /metrics/fitness               # CTL/ATL/TSB (query param: threshold_method)
  GET    /metrics/power-curve           # Critical power curve
  GET    /metrics/totals                # Daily/weekly/monthly rollups

Thresholds:
  GET    /thresholds                    # User's threshold history
  POST   /thresholds                    # Add new threshold
  PUT    /thresholds/{id}/activate      # Set as active method

Integrations:
  GET    /integrations/strava/authorize # OAuth2 flow start
  GET    /integrations/strava/callback  # OAuth2 callback
  POST   /integrations/strava/sync      # Manual sync trigger
  POST   /webhooks/strava               # Strava webhook receiver
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-1K users** | Single server monolith: API + Workers + DB + Redis in Docker Compose. Vertical scaling (bigger server). |
| **1K-10K users** | Separate worker server (horizontal worker scaling). Add read replica for PostgreSQL. Redis persistence for cache durability. CDN for frontend assets. |
| **10K-100K users** | Horizontal API scaling (multiple FastAPI instances behind load balancer). Dedicated TimescaleDB instance (managed service). Redis cluster for cache. Background job prioritization (separate high/low priority workers). |
| **100K+ users** | Consider service extraction (import service, compute service, API service). Multi-region PostgreSQL (geo-distributed users). Kafka for event streaming (replace Celery for high-throughput). GraphQL for complex queries. |

### First Bottleneck: Database Writes (Activity Uploads)

**Symptom:** Slow FIT file uploads, locked activity_streams table during inserts.

**Solution:**
1. Batch inserts (bulk INSERT 1000+ rows at once, not 1 row at a time)
2. Increase TimescaleDB chunk_time_interval if too many small chunks
3. Horizontal worker scaling (more Celery workers processing uploads in parallel)
4. Database connection pooling (SQLAlchemy pool_size=20)

**Implementation:**
```python
# Batch insert activity streams (1000x faster than row-by-row)
def save_activity_streams(activity_id, streams):
    rows = [
        {
            "activity_id": activity_id,
            "timestamp": stream.timestamp,
            "power_watts": stream.power,
            "heart_rate": stream.hr,
        }
        for stream in streams
    ]

    # Bulk insert 3600 rows in one transaction
    db.bulk_insert_mappings(ActivityStream, rows)
    db.commit()
```

### Second Bottleneck: Dashboard Load Times (Metric Queries)

**Symptom:** Slow fitness chart loading (CTL/ATL/TSB computation on full history).

**Solution:**
1. Pre-compute with continuous aggregates (daily_tss already rolled up)
2. Redis caching (5 min TTL for fitness data)
3. Lazy loading (fetch last 90 days first, load more on scroll)
4. Query optimization (index on user_id, activity_date)

**Implementation:**
```sql
-- Index for fast user activity queries
CREATE INDEX idx_activities_user_date ON activities(user_id, activity_date DESC);

-- Continuous aggregate for fast fitness queries
CREATE MATERIALIZED VIEW fitness_daily
WITH (timescaledb.continuous) AS
SELECT
  user_id,
  time_bucket('1 day', activity_date) AS day,
  SUM(tss) as tss,
  AVG(intensity_factor) as if_avg
FROM activities
GROUP BY user_id, day;
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Computed Metrics Only in Redis

**What people do:** Cache CTL/ATL/TSB in Redis, never persist to database. Treat Redis as source of truth.

**Why it's wrong:**
- Redis evicts data (memory limits, restarts)
- Cache invalidation loses data permanently
- Cannot query historical trends ("show me CTL on this date 6 months ago")

**Do this instead:**
- Store computed metrics in `fitness_metrics` table (source of truth)
- Use Redis as read-through cache (cache miss → query DB → cache result)
- Cache invalidation just forces recomputation, doesn't lose data

### Anti-Pattern 2: Over-Normalizing Activity Streams

**What people do:** Create separate tables for `power_streams`, `hr_streams`, `cadence_streams` to be "normalized."

**Why it's wrong:**
- Time-series data accessed together (when showing activity detail, need all streams)
- Forces 4+ JOIN operations for every activity view
- Breaks TimescaleDB hypertable benefits (can't partition multiple tables as one)

**Do this instead:**
- Store all streams in single `activity_streams` hypertable with nullable columns
- Partition by time (timestamp), not by metric type
- Query filters on activity_id (indexes well, stays in same chunk)

### Anti-Pattern 3: Recalculating All Metrics on Every Activity Upload

**What people do:** Recompute CTL/ATL/TSB for entire user history every time an activity is added.

**Why it's wrong:**
- Exponentially slower as user history grows (1000 activities = 1000 recalculations per upload)
- Blocks activity uploads (user waits 30 seconds for computation)

**Do this instead:**
- Incremental computation: Only recalculate from new activity date forward
- Cache intermediate results (yesterday's CTL is input to today's CTL)
- Background computation: Return activity_id immediately, compute async

```python
# Bad: Recalculate entire history
def recompute_fitness(user_id):
    activities = get_all_activities(user_id)  # 1000 activities
    for activity in activities:
        ctl, atl = compute_fitness(activity, previous_ctl, previous_atl)
    # Takes 30 seconds

# Good: Incremental update
def update_fitness_from_activity(user_id, new_activity):
    # Fetch yesterday's CTL/ATL (1 row)
    prev = get_fitness_metrics(user_id, new_activity.date - 1)

    # Compute today's CTL/ATL (using exponential moving average formula)
    new_ctl = prev.ctl + (new_activity.tss - prev.ctl) * (1 - exp(-1/42))
    new_atl = prev.atl + (new_activity.tss - prev.atl) * (1 - exp(-1/7))

    # Store result (1 row insert)
    save_fitness_metrics(user_id, new_activity.date, new_ctl, new_atl)
    # Takes <10ms
```

### Anti-Pattern 4: Using Regular Timestamps Instead of TimescaleDB's time_bucket

**What people do:** Query activity_streams directly with manual date grouping.

```sql
-- Bad: Manual grouping, full table scan
SELECT
  DATE_TRUNC('minute', timestamp) as minute,
  AVG(power_watts) as avg_power
FROM activity_streams
WHERE activity_id = 123
GROUP BY DATE_TRUNC('minute', timestamp);
```

**Why it's wrong:**
- Doesn't leverage hypertable partitioning
- Slower aggregation (no continuous aggregates)

**Do this instead:**
```sql
-- Good: Use time_bucket, can create continuous aggregate
SELECT
  time_bucket('1 minute', timestamp) as minute,
  AVG(power_watts) as avg_power
FROM activity_streams
WHERE activity_id = 123
GROUP BY minute
ORDER BY minute;
```

### Anti-Pattern 5: Monolithic API Routes

**What people do:** Put all activity logic in single `activities.py` router (500+ lines).

**Why it's wrong:**
- Merge conflicts in team development
- Hard to test (one giant router)
- Mixes concerns (auth, upload, metrics, visualization)

**Do this instead:**
```python
# Separate routers by domain
routers/
  ├── activities.py        # CRUD: list, get, delete
  ├── uploads.py           # File upload, parsing
  ├── metrics.py           # Fitness analytics
  ├── streams.py           # Second-by-second data
  └── integrations.py      # Strava, Garmin OAuth

# main.py includes all
app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Strava API** | OAuth2 + webhooks | Rate limit: 100 requests/15min, 1000/day per user. Use webhooks for real-time sync. |
| **Garmin Connect** | No official API | Use python-garmin-connect library (unofficial). Credentials-based auth. Less reliable. |
| **OpenStreetMap Tiles** | HTTPS tile server | Use free OSM tiles for dev, self-host tile server (Tile Server GL) for production. |
| **Redis** | Direct connection (aioredis) | Use for cache + Celery broker. Enable persistence (AOF) for production. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **API ↔ Service Layer** | Direct function calls | Same process, synchronous. Service returns data, router serializes to JSON. |
| **API ↔ Workers** | Celery tasks (Redis queue) | Async, fire-and-forget. API returns task_id, frontend polls for status. |
| **Workers ↔ Database** | SQLAlchemy ORM | Use sync engine for Celery workers (simpler than async in worker context). |
| **Frontend ↔ API** | REST over HTTPS | JWT in Authorization header. CORS enabled for local dev. |
| **Frontend ↔ Map Tiles** | HTTPS (Leaflet) | Direct browser → tile server. No proxy through API. |

## Sources

### TimescaleDB & Time-Series Architecture
- [GitHub - timescale/timescaledb](https://github.com/timescale/timescaledb)
- [Tiger Data: PostgreSQL++ for Time Series](https://www.tigerdata.com)
- [Fastest PostgreSQL for real-time analytics | Timescale](https://www.timescale.com/)
- [How to Create Hypertables in TimescaleDB](https://oneuptime.com/blog/post/2026-02-02-timescaledb-hypertables/view)
- [Scaling Time Series Data with TimescaleDB Hypertables](https://www.cloudthat.com/resources/blog/scaling-time-series-data-with-timescaledb-hypertables)
- [Real-Time Analytics for Time Series: Continuous Aggregates](https://www.tigerdata.com/blog/real-time-analytics-for-time-series-continuous-aggregates)
- [How to Use TimescaleDB Continuous Aggregates](https://oneuptime.com/blog/post/2026-01-27-timescaledb-continuous-aggregates/view)

### Self-Hosted Fitness Platforms
- [GitHub - endurain-project/endurain](https://github.com/joaovitoriasilva/endurain)
- [GitHub - SamR1/FitTrackee](https://github.com/SamR1/FitTrackee)
- [This self-hosted fitness tracking service](https://www.xda-developers.com/self-hosted-fitness-tracking-service/)

### FIT File Processing
- [GitHub - dtcooper/python-fitparse](https://github.com/dtcooper/python-fitparse)
- [python-fitparse Documentation](https://dtcooper.github.io/python-fitparse/)
- [GitHub - garmin/fit-python-sdk](https://github.com/garmin/fit-python-sdk)
- [FIT SDK | Garmin Developers](https://developer.garmin.com/fit/example-projects/python/)

### Background Job Processing
- [Celery 2026: Python Distributed Task Queue](https://www.programming-helper.com/tech/celery-2026-python-distributed-task-queue-redis-rabbitmq)
- [7 Celery/RQ Patterns That Dramatically Simplify Python Services](https://medium.com/@connect.hashblock/7-celery-rq-patterns-that-dramatically-simplify-python-services-9d31ace5f42a)
- [Python Background Tasks 2025: Celery, RQ, or Dramatiq?](https://devproportal.com/languages/python/python-background-tasks-celery-rq-dramatiq-comparison-2025/)
- [Orchestrating a Background Job Workflow in Celery](https://www.toptal.com/python/orchestrating-celery-python-background-jobs)

### Caching Strategies
- [Caching patterns - Database Caching Strategies Using Redis](https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html)
- [Redis Cache in 2026: Fast Paths, Fresh Data](https://thelinuxcode.com/redis-cache-in-2026-fast-paths-fresh-data-and-a-modern-dx/)
- [Database Caching with Redis: Strategies for Optimization](https://www.site24x7.com/learn/redis-database-caching.html)

### FastAPI Best Practices
- [GitHub - zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [FastAPI Best Practices for Production: Complete 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [How to Structure Your FastAPI Projects](https://medium.com/@amirm.lavasani/how-to-structure-your-fastapi-projects-0219a6600a8f)
- [FastAPI - Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

### Authentication Patterns
- [Implementing Secure User Authentication in FastAPI using JWT](https://neon.com/guides/fastapi-jwt)
- [Authentication and Authorization with FastAPI: A Complete Guide](https://betterstack.com/community/guides/scaling-python/authentication-fastapi/)
- [Securing FastAPI with JWT Token-based Authentication](https://testdriven.io/blog/fastapi-jwt-auth/)
- [OAuth2 with Password and JWT tokens - FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

### API Design & Architecture
- [REST API vs GraphQL: What Enterprises Should Choose in 2026?](https://www.bizdata360.com/rest-api-vs-graphql/)
- [GraphQL vs REST API: Which is Better for Your Project in 2025?](https://api7.ai/blog/graphql-vs-rest-api-comparison-2025)
- [Monolithic vs Microservices Architecture](https://blog.binaryrepublik.com/2026/02/modular-monolith-vs-microservices.html)
- [Microservices vs Monoliths in 2026: When Each Architecture Wins](https://www.javacodegeeks.com/2025/12/microservices-vs-monoliths-in-2026-when-each-architecture-wins.html)

### Docker Multi-Service Deployment
- [Tiger Data Documentation | Install TimescaleDB on Docker](https://docs.timescale.com/self-hosted/latest/install/installation-docker/)
- [GitHub - chuckwilliams37/mcp-server-docker](https://github.com/chuckwilliams37/mcp-server-docker)
- [timescale/timescaledb - Docker Image](https://hub.docker.com/r/timescale/timescaledb)

### Frontend & Data Visualization
- [15 Best React JS Chart Libraries in 2026](https://technostacks.com/blog/react-chart-libraries/)
- [Best Chart Libraries for Svelte Projects in 2026](https://weavelinx.com/best-chart-libraries-for-svelte-projects-in-2026/)
- [Svelte vs React 2026: Which Framework Should You Choose?](https://devtrios.com/blog/svelte-vs-react-which-framework-should-you-choose/)
- [Building a Real-time Dashboard with FastAPI and Svelte](https://testdriven.io/blog/fastapi-svelte/)

### Geospatial & Cycling Maps
- [Leveraging OpenStreetMap with PostGIS](https://medium.com/@supulkalhara7/leveraging-openstreetmap-with-postgis-a-seamless-integration-for-geopatial-data-handling-with-25df44319be9)
- [CyclOSM - OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/CyclOSM)
- [CyclOSM: OpenStreetMap-based bicycle map](https://www.cyclosm.org/)
- [Leaflet - JavaScript library for interactive maps](https://leafletjs.com/)

### Strava Integration
- [Webhook Events API - Strava](https://developers.strava.com/docs/webhooks/)
- [Getting Started with the Strava API](https://developers.strava.com/docs/getting-started/)
- [How to get your data from the Strava API using Python and stravalib](https://stravalib.readthedocs.io/en/v2.2/get-started/how-to-get-strava-data-python.html)

---
*Architecture research for: Cycling Analytics Platform*
*Researched: 2026-02-10*
