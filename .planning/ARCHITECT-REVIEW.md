# ARCHITECT REVIEW

**Reviewed:** 2026-02-10
**Reviewer:** Architecture Agent (Opus)
**Scope:** PLANS.md (Phases 1-8, 42 plans) against ROADMAP.md, REQUIREMENTS.md, SUMMARY.md, ARCHITECTURE.md, PITFALLS.md, and 01-CONTEXT.md
**Key Constraint Verified:** PostgreSQL + TimescaleDB + PostGIS on NAS; Docker only for app, worker, Redis, Nginx

---

## Verdict: APPROVED_WITH_NOTES

The plans are comprehensive, well-structured, and demonstrate strong alignment with the research phase outputs. The 42 plans across 8 phases cover all v1 requirements mapped in REQUIREMENTS.md, and the technical approaches are sound. The NAS database constraint is correctly handled throughout. However, there are several issues ranging from critical to minor that should be addressed before or during execution.

---

## Strengths

### 1. Exceptional Precision Discipline
The NUMERIC type commitment is threaded through every plan that touches power data -- from Plan 1.2 (schema) through Plan 2.4 (CTL/ATL/TSB storage) to the cross-phase "Precision Guarantee Chain" section. The plans explicitly call out "no FLOAT/REAL/DOUBLE types" in acceptance criteria and document the full chain: INT in streams -> NUMERIC in computed metrics -> string-formatted decimals in API -> fixed-precision display. This directly addresses Pitfall 1 (floating-point precision) which was flagged as HIGH recovery cost.

### 2. Correct NAS Database Handling
The key constraint is respected consistently. Plan 1.3 explicitly states "NO database service in docker-compose -- DB is external on NAS." The DATABASE_URL uses `postgresql+asyncpg://user:pass@NAS_IP:5432/cycling_analytics`. Dev compose only runs Redis. Production compose runs api, worker, redis, nginx -- no PostgreSQL. Environment variables (DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME) are parameterized for NAS connection. This is correct and consistent across all plans.

### 3. Thorough Pitfall Coverage
All 8 pitfalls from SUMMARY.md are explicitly addressed:
- Pitfall 1 (float precision): NUMERIC types throughout, integer watts in streams
- Pitfall 2 (FIT device variability): python-fitparse with graceful degradation, device matrix testing
- Pitfall 3 (chunk misconfiguration): 90-day chunk_time_interval specified in Plan 1.2
- Pitfall 4 (Strava rate limits): webhooks (Plan 3.3), rate limiter service (Plan 3.2), exponential backoff
- Pitfall 5 (NP edge cases): minimum duration check, dropout handling, spike detection (Plan 2.1)
- Pitfall 6 (PostGIS confusion): GEOGRAPHY(POINT, 4326) from Plan 1.2, geoalchemy2 usage
- Pitfall 7 (FTP instability): ftp_at_computation stored per metric (Plan 2.3), threshold history (Plan 4.1)
- Pitfall 8 (RLS performance): Application-level isolation with composite indexes (Plan 5.2), not PostgreSQL RLS

### 4. Well-Designed Migration Sequence
The 9-migration sequence is logically ordered with no circular dependencies. Each migration builds on the previous schema without requiring backfill operations. The cross-phase concern section documents this clearly.

### 5. Incremental Fitness Computation
Plan 2.4 correctly implements incremental CTL/ATL/TSB updates (recalculate only from changed date forward) rather than the anti-pattern of full-history recomputation on every activity. The EWMA formulas are mathematically correct.

### 6. Multi-Method Threshold Pre-Caching
Plan 4.4 pre-computes metrics for ALL threshold methods on import, enabling instant UI switching. This directly satisfies THRS-06 and THRS-07 without on-demand recomputation, which is the right architectural choice for a self-hosted platform where storage is cheap.

---

## Issues

### CRITICAL

#### C1: Chunk Time Interval Contradiction Between Plans and Architecture Research
- **Phase/Plan:** Plan 1.2 vs ARCHITECTURE.md
- **Problem:** Plan 1.2 specifies `chunk_time_interval => INTERVAL '90 days'` based on SUMMARY.md research guidance (optimized for 1Hz data with 16GB RAM). However, ARCHITECTURE.md shows `chunk_time_interval => INTERVAL '1 week'` in both the example schema (line 332) and the chunk interval guidance section (line 685-686: "1 week chunks for activity_streams"). The Plans correctly chose 90 days, but if an implementer references ARCHITECTURE.md during execution, they will see conflicting guidance.
- **Recommendation:** During Phase 1.2 execution, treat the 90-day interval from PLANS.md as authoritative. Add a note to ARCHITECTURE.md or the phase context clarifying that the 1-week example was a generic illustration and the calculated interval for this workload is 90 days. The 90-day figure is correct for 7+ years of 1Hz data at ~150-200 rides/year.

#### C2: Celery Worker Uses asyncpg Connection String but Needs Sync Engine
- **Phase/Plan:** Plan 1.4, Plan 1.6
- **Problem:** Plan 1.4 states "Celery worker runs with sync SQLAlchemy engine (not async) per architecture guidance." This is correct -- Celery workers should use synchronous database access. However, the DATABASE_URL throughout the plans uses `postgresql+asyncpg://...` (the async driver). The Celery worker needs a separate connection string using `postgresql+psycopg2://...` (or `postgresql://...` for psycopg). This is not addressed anywhere in the plans.
- **Recommendation:** Plan 1.4 must include creating a separate `SYNC_DATABASE_URL` environment variable using `postgresql+psycopg2://` or `postgresql://` driver for the Celery worker. Add `psycopg2-binary` (or `psycopg[binary]`) to the dependencies in Plan 1.1. The worker's `database.py` should have a separate sync engine factory. This is a blocking issue -- without it, the Celery worker cannot connect to the database.

#### C3: Missing Lap Data Storage
- **Phase/Plan:** Plan 1.5, Plan 1.2
- **Problem:** Plan 1.5 (FIT parser) explicitly extracts lap data: "Extract from `lap` messages: start_time, total_elapsed_time, total_distance, avg_power, max_power, avg_heart_rate, max_heart_rate." The parser returns `list[LapRecord]`. However, there is no `activity_laps` table defined in Plan 1.2's migration, no model file for laps, and no storage of lap data in Plan 1.6's import pipeline. ARCHITECTURE.md lists `activity_laps` as a hypertable. The parsed lap data is extracted but silently discarded.
- **Recommendation:** Add an `activity_laps` table to migration 001 in Plan 1.2. Create `backend/app/models/activity_lap.py`. Update Plan 1.6 to store lap records during import. Lap data is valuable for interval analysis in Phase 7 and for future automatic interval detection (V2-01). Consider whether this should be a hypertable (ARCHITECTURE.md says yes) or a regular table (laps are low-volume, ~10-50 per activity, accessed by activity_id not time range -- regular table is more appropriate).

### MAJOR

#### M1: Strava Rate Limits Quoted Incorrectly in Plans vs Research
- **Phase/Plan:** Plan 3.2, SUMMARY.md, ARCHITECTURE.md
- **Problem:** The plans and SUMMARY.md quote Strava rate limits as "200 requests/15min, 2000/day" (Plan 3.2 line 766, SUMMARY.md Pitfall 4, ROADMAP.md Phase 3 success criteria). However, ARCHITECTURE.md line 1082 shows "100 requests/15min, 1000/day per user." The official Strava documentation (as of 2025) states 200/15min and 2000/day as the default, so the plans are correct. ARCHITECTURE.md has the wrong numbers.
- **Recommendation:** No change needed in PLANS.md. Correct ARCHITECTURE.md during implementation to avoid confusion. The rate limiter in Plan 3.2 should track both windows (15-min and daily) using the correct limits.

#### M2: Compression Policy of 7 Days May Be Too Aggressive
- **Phase/Plan:** Plan 1.2
- **Problem:** The compression policy compresses chunks after 7 days. For a self-hosted platform where the user is actively analyzing recent rides, 7 days is aggressive. Decompressing chunks for queries on rides from last week adds latency. Most users will regularly review rides from the past 2-4 weeks for training analysis. TimescaleDB decompression for reads is transparent but slower than uncompressed access.
- **Recommendation:** Change the compression policy to 30 days instead of 7 days. This keeps the most-analyzed data uncompressed (last month of rides) while still achieving good compression ratios for older data. The storage cost difference is minimal for a self-hosted NAS with presumably ample disk space. Adjust to: `SELECT add_compression_policy('activity_streams', INTERVAL '30 days');`

#### M3: No FTP/Settings API Endpoint in Phase 2 Plans
- **Phase/Plan:** Phase 2 Verification, Plan 2.2
- **Problem:** The Phase 2 verification script references `POST http://localhost:8000/settings/ftp` to set FTP, but no plan in Phase 2 creates a `/settings/ftp` endpoint. Plan 2.2 creates the `UserSettings` model with `ftp_watts`, but there is no router or schema for updating it. Plan 4.5 creates `/settings` endpoints, but that is Phase 4 -- two phases later. Phase 2 cannot be verified as written because there is no way to set FTP via API.
- **Recommendation:** Add a minimal FTP endpoint to Plan 2.2 or create a small Plan 2.2b: `POST /settings/ftp` (just FTP, not full settings). This unblocks Phase 2 verification and testing. Alternatively, fold a simple `PUT /settings` into Plan 2.2 and reduce the scope of Plan 4.5 to just threshold method selection.

#### M4: THRS-04 (Xert Threshold Model) Listed in Phase 4 Requirements but Not Planned
- **Phase/Plan:** Phase 4, ROADMAP.md
- **Problem:** ROADMAP.md Phase 4 Success Criteria #4 states: "System estimates threshold using Xert model (dynamic, changes daily)." The requirements traceability maps THRS-04 to Phase 4. However, PLANS.md Phase 4 only covers manual, 95% of 20-min, and 90% of 8-min methods. The Xert threshold model is acknowledged in Plan 4.1 (threshold methods enum includes `xert_model`) but is explicitly noted as "Phase 10" with no implementation plan. Phase 4 cannot satisfy its own success criteria or THRS-04 as planned.
- **Recommendation:** Two options: (a) Move THRS-04 from Phase 4 to Phase 10 in the ROADMAP.md success criteria and requirements traceability, reflecting the actual plan. This is the recommended approach since Xert algorithms are deferred to Phase 9-10 by design. (b) Add a stub plan in Phase 4 that prepares the data model for Xert but defers actual algorithm implementation. Option (a) is cleaner.

#### M5: No Upload Rate Limiting
- **Phase/Plan:** Plan 1.6
- **Problem:** PITFALLS.md Security Mistakes section explicitly warns: "Not rate-limiting FIT file uploads -- Attacker uploads 1000s of files, fills disk or burns processing quota. Limit to 10 uploads/hour per user, validate file size < 10MB." Plan 1.6 does not mention any upload rate limiting or file size validation. While multi-user is Phase 5, the upload infrastructure should include these protections from the start.
- **Recommendation:** Add to Plan 1.6: (1) File size validation -- reject files > 50MB (generous for FIT files, which are typically 1-5MB). (2) Rate limiting -- 20 uploads/hour per user (or per IP in Phase 1 before auth exists). (3) File type validation -- verify FIT magic bytes, not just extension. These are straightforward to implement and prevent abuse.

#### M6: No Continuous Aggregates in Plans
- **Phase/Plan:** All phases
- **Problem:** ARCHITECTURE.md heavily features continuous aggregates as a key architectural pattern: `daily_totals`, `weekly_fitness`, `monthly_stats`, `power_curve_cache` are called out as continuous aggregates. SUMMARY.md lists them under Phase 4 deliverables. However, PLANS.md never creates a single continuous aggregate. The totals page (Plan 8.4) uses `time_bucket` in queries but does not materialize these as continuous aggregates. The fitness chart (Plan 8.1) relies on the `daily_fitness` regular table. The power curve (Plan 8.2) uses Redis caching.
- **Recommendation:** This is a defensible architectural choice -- the plans use a combination of pre-computed tables (daily_fitness) and Redis caching instead of continuous aggregates. For a single-user or low-user-count self-hosted platform, this is adequate. However, add a note to Phase 8 or the cross-phase concerns explaining why continuous aggregates were deferred (complexity vs benefit for self-hosted use case). Consider adding them as a performance optimization if query times exceed targets during Phase 8 verification.

#### M7: Missing Data Export Capability
- **Phase/Plan:** All phases
- **Problem:** PITFALLS.md "Looks Done But Isn't" checklist includes "Data Export: Often missing FIT file reconstruction, Strava upload support, TCX/GPX format conversion -- users expect to download their data." No plan in Phases 1-8 addresses data export. For a self-hosted privacy-first platform, data portability is arguably table stakes. Users should be able to export their data.
- **Recommendation:** Add a plan (or extend Plan 1.10) to include: (1) Download original FIT file for any activity. (2) Export activity list as CSV. These are minimal-effort additions that significantly improve the user experience for a data-ownership-focused platform. TCX/GPX export can be deferred to v2.

### MINOR

#### m1: Health Endpoint Missing Disk Space Check
- **Phase/Plan:** Plan 1.1
- **Problem:** Plan 1.1 acceptance criteria state health check returns `{"status": "healthy", "database": "connected", "redis": "connected"}`. The plan also mentions "disk space" in the health router description. However, the acceptance criteria response schema does not include disk space. For a self-hosted NAS platform where FIT file storage is local, disk space monitoring is important.
- **Recommendation:** Include disk space in the health check response: `{"status": "healthy", "database": "connected", "redis": "connected", "disk_free_gb": 142.7}`. This takes < 30 minutes to implement and provides important operational visibility.

#### m2: Frontend Store for Metrics Not Used Until Phase 8
- **Phase/Plan:** Plan 6.1
- **Problem:** Plan 6.1 creates `metricsStore.ts` as part of initial frontend setup, but metrics are not displayed until Phase 8. Creating unused stores clutters the initial codebase.
- **Recommendation:** Move `metricsStore.ts` creation to Plan 8.1 when it is actually needed. Minor organizational preference.

#### m3: Test Fixture Strategy Not Defined
- **Phase/Plan:** Plan 1.5
- **Problem:** Plan 1.5 mentions `backend/tests/fixtures/` for test FIT files from "various Garmin devices" but does not explain how these fixtures are obtained or managed. FIT files contain personal GPS and health data. They should not be committed to the repository without sanitization.
- **Recommendation:** Add a note about test fixture strategy: (1) Use synthetic/anonymized FIT files for CI. (2) Document which devices are covered. (3) Add the fixtures directory to `.gitignore` if using real personal files, or create a fixture generation script.

#### m4: Alembic Async Migration May Need Special Handling
- **Phase/Plan:** Plan 1.2
- **Problem:** Plan 1.2 states Alembic uses async migration support with the `asyncpg` driver. Alembic's async support requires specific `env.py` configuration with `run_async()` and `connectable.run_sync()`. The plan mentions this but does not detail the `op.execute()` calls for TimescaleDB extension creation and hypertable setup, which are DDL operations that run differently in async vs sync Alembic contexts.
- **Recommendation:** Ensure the Plan 1.2 implementer uses Alembic's `run_async()` pattern and tests that `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")` works correctly in the async migration runner. Alternatively, use a sync connection for migrations (simpler, and migrations are one-time operations).

#### m5: Redis Database Number Conflict
- **Phase/Plan:** Plan 1.4
- **Problem:** Plan 1.4 specifies `broker=redis://redis:6379/0, backend=redis://redis:6379/1`. Plan 2.5 uses Redis for caching. If the cache also uses database 0 or 1, there could be key collisions with Celery's internal keys. The cache key patterns (`fitness:{user_id}`) would coexist with Celery broker messages in the same Redis database.
- **Recommendation:** Use separate Redis databases: db0 for Celery broker, db1 for Celery results, db2 for application cache. Document this in `.env.example`. This is a minor naming concern but prevents subtle bugs.

#### m6: Plan 1.9 Duplicate Detection Logic is Overly Generous
- **Phase/Plan:** Plan 1.9
- **Problem:** Manual entry duplicate detection uses "same user + same date + same duration = prompt for confirmation." For CSV imports with hundreds of rows, prompting for each potential duplicate is impractical. The behavior should differ between single manual entry (prompt) and bulk CSV import (auto-skip or flag).
- **Recommendation:** For CSV import: auto-skip duplicates and include them in the response's "skipped" list with reason. For single manual entry via API: return a warning in the response that the client can display, with a `force=true` parameter to override.

#### m7: Activity Streams Table Missing Foreign Key Enforcement Strategy
- **Phase/Plan:** Plan 1.2
- **Problem:** The `activity_streams` hypertable has `activity_id INT NOT NULL` referencing `activities(id)`. TimescaleDB hypertables do not support foreign key constraints pointing INTO the hypertable, but foreign keys FROM the hypertable to regular tables are supported with caveats. However, ON DELETE CASCADE from activities to activity_streams needs explicit handling since cascading deletes on hypertables can be slow.
- **Recommendation:** Document the FK strategy: (1) Keep the FK constraint for data integrity. (2) When deleting an activity (Plan 1.6 DELETE endpoint), explicitly delete streams first in a batch (`DELETE FROM activity_streams WHERE activity_id = X`), then delete the activity. This avoids slow cascade behavior on large hypertable chunks. (3) Consider whether the FK should be deferred or not enforced at the database level (rely on application logic).

---

## Missing Coverage

### Gap 1: No Error/Retry UI in Frontend
Phases 6-8 build frontend views but do not include error handling patterns for failed uploads, sync failures, or computation errors. Plan 6.3 mentions "error handling" in the upload flow but no dedicated error state management. A failed Garmin sync or Strava rate limit should be surfaced to the user.

### Gap 2: No Monitoring or Logging Strategy
No plan addresses structured logging, log aggregation, or monitoring. For a self-hosted platform, at minimum: (1) Structured JSON logging from FastAPI and Celery. (2) Log rotation for Docker containers. (3) Basic Celery task monitoring (Flower or similar). This is important for debugging sync failures and parser issues.

### Gap 3: No Database Backup Strategy
The database lives on a NAS, outside Docker. No plan addresses backup/restore procedures, which is critical for a self-hosted platform. At minimum, document how to run `pg_dump` against the NAS database and recommend a cron schedule.

### Gap 4: No Activity Edit/Update Capability
Users can create, view, and delete activities but cannot edit them. Common need: correcting activity name, adding notes after import, fixing sport type. This is a small gap but affects usability.

### Gap 5: Strava Webhook URL Public Accessibility
Plan 3.3 acknowledges "Webhook URL must be publicly accessible" but does not plan for how a self-hosted NAS platform achieves this. The user needs a reverse proxy, dynamic DNS, or tunnel (ngrok). This is a deployment concern that should at least be documented.

---

## Recommendations

### R1: Address Critical C2 (Sync Database URL) Before Execution
This is a blocking issue for Plan 1.4 and all subsequent Celery worker plans. Add `psycopg2-binary` or `psycopg[binary]` to dependencies in Plan 1.1, and create a `SYNC_DATABASE_URL` environment variable pattern. Estimate: 15 minutes of additional planning, prevents hours of debugging.

### R2: Move THRS-04 to Phase 10 in ROADMAP.md
The Xert threshold model cannot be implemented until Xert algorithms are reverse-engineered in Phase 9-10. Update ROADMAP.md Phase 4 success criteria to remove criterion #4, and add it to Phase 10. This keeps the roadmap honest.

### R3: Add a "Plan 1.2b: Lap Table and Activity Edit" Mini-Plan
Incorporate lap storage and basic activity metadata editing (PATCH /activities/{id}) into the Phase 1 migration. Cost: small. Benefit: prevents a migration addition later and enables Phase 7 interval analysis.

### R4: Implement Compression at 30 Days, Not 7
Change `add_compression_policy('activity_streams', INTERVAL '30 days')` for a better user experience on recent ride analysis. Storage impact is minimal on a NAS.

### R5: Add FIT File Download Endpoint to Plan 1.10
Simple addition: `GET /activities/{id}/fit-file` returns the original FIT file. The file is already stored (Plan 1.6). This satisfies data portability expectations and takes < 1 hour to implement.

### R6: Document the Continuous Aggregates Decision
Add a paragraph to the cross-phase concerns explaining that continuous aggregates were evaluated but deferred in favor of pre-computed tables + Redis cache for the self-hosted use case. This prevents future reviewers from flagging the omission as an oversight.

### R7: Add Minimal Logging to Plan 1.1
Include `structlog` or `python-json-logger` in Plan 1.1 dependencies. Configure structured JSON logging in FastAPI's lifespan handler. This costs almost nothing upfront and saves significant debugging time later.

---

## Summary Metrics

| Category | Count |
|----------|-------|
| Plans reviewed | 42 |
| Requirements covered | 42/42 (with THRS-04 caveat) |
| Pitfalls addressed | 8/8 |
| Critical issues | 3 |
| Major issues | 7 |
| Minor issues | 7 |
| Missing coverage gaps | 5 |
| Recommendations | 7 |

---

*Review completed: 2026-02-10*
*Verdict: APPROVED_WITH_NOTES -- Address C2 (sync DB URL) and C3 (lap storage) before Phase 1 execution begins. All other issues can be resolved during implementation.*
