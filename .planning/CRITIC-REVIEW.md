# CRITIC REVIEW

**Reviewed:** 2026-02-10
**Scope:** PLANS.md (Phases 1-8, 42 plans), ROADMAP.md (11 phases), REQUIREMENTS.md (42 v1 requirements), 01-CONTEXT.md (Phase 1 decisions)

---

## Verdict: APPROVED_WITH_NOTES

The plans are thorough, well-structured, and cover the vast majority of requirements with clear technical approaches and testable acceptance criteria. The level of detail is impressive -- file lists, algorithm pseudocode, edge case handling, and verification scripts are all present. However, several issues need attention before execution begins, ranging from an architectural contradiction in Docker deployment to missing coverage for Xert-based threshold estimation and some acceptance criteria that are not independently testable.

---

## Requirement Coverage Matrix

| Requirement ID | Plan(s) | Covered | Notes |
|---------------|---------|---------|-------|
| DATA-01 | 1.5, 1.6, 1.7, 1.8 | Y | FIT import, zip archive, Garmin sync all covered |
| DATA-02 | 3.1, 3.2, 3.3, 3.4 | Y | Full Strava OAuth, sync, webhook, backfill |
| DATA-03 | 1.2, 1.6 | Y | TimescaleDB hypertable with 1Hz stream data |
| DATA-04 | 1.2, 1.6 | Y | Activity metadata in PostgreSQL |
| DATA-05 | 1.6 | Y | Original FIT files preserved at `{FIT_STORAGE_PATH}/{user_id}/{YYYY}/{MM}/{uuid}.fit` |
| METR-01 | 2.1 | Y | NP with edge cases (short rides, dropouts, spikes) |
| METR-02 | 2.2 | Y | IF = NP / FTP |
| METR-03 | 2.2 | Y | TSS formula implemented |
| METR-04 | 2.4 | Y | CTL 42-day EWMA |
| METR-05 | 2.4 | Y | ATL 7-day EWMA |
| METR-06 | 2.4 | Y | TSB = CTL - ATL |
| METR-07 | 2.2 | Y | 7-zone Coggan model with zone boundaries |
| XERT-01 | -- | N | Deferred to Phase 9 (not planned yet). Acceptable. |
| XERT-02 | -- | N | Deferred to Phase 9. Acceptable. |
| XERT-03 | -- | N | Deferred to Phase 9. Acceptable. |
| XERT-04 | -- | N | Deferred to Phase 10. Acceptable. |
| XERT-05 | -- | N | Deferred to Phase 10. Acceptable. |
| XERT-06 | -- | N | Deferred to Phase 10. Acceptable. |
| XERT-07 | -- | N | Deferred to Phase 10. Acceptable. |
| THRS-01 | 4.1 | Y | Manual FTP setting |
| THRS-02 | 4.2 | Y | 95% of 20-min best |
| THRS-03 | 4.3 | Y | 90% of 8-min best |
| THRS-04 | -- | **PARTIAL** | Listed in Phase 4 enum (`xert_model`) but **no plan implements it**. Phase 4 only covers manual/pct_20min/pct_8min. Xert model is Phase 10 dependency. |
| THRS-05 | 4.5 | Y | User selects preferred method in settings |
| THRS-06 | 4.4 | Y | Pre-compute metrics for all methods |
| THRS-07 | 4.4 | Y | Instant switching via pre-cached data |
| THRS-08 | 4.1, 2.3 | Y | ftp_at_computation stored per metric record |
| ACTV-01 | 6.3 | Y | Sortable activity table |
| ACTV-02 | 6.4 | Y | Activity detail with timeline plot |
| ACTV-03 | 7.1 | Y | 30-second zone shading |
| ACTV-04 | 7.2 | Y | Power analysis page |
| ACTV-05 | 7.3 | Y | HR analysis page |
| ACTV-06 | 7.4 | Y | Route map with Leaflet + OSM |
| DASH-01 | 8.1 | Y | Fitness chart (PMC) with date range and method switching |
| DASH-02 | 8.2 | Y | Critical power curve |
| DASH-03 | 8.3 | Y | Calendar with configurable start day |
| DASH-04 | 8.3 | Y | Weekly summary stats in calendar |
| DASH-05 | 8.4 | Y | Totals page with weekly/monthly/yearly |
| PLAN-01 | -- | N | Deferred to Phase 11. Acceptable. |
| PLAN-02 | -- | N | Deferred to Phase 11. Acceptable. |
| PLAN-03 | -- | N | Deferred to Phase 11. Acceptable. |
| INFR-01 | 5.1, 5.2, 5.3 | Y | Auth, data isolation, profiles |
| INFR-02 | 1.3 | Y | Docker Compose deployment |
| INFR-03 | 1.2, 2.1, 2.2, 2.3, 2.4 | Y | NUMERIC types throughout |
| INFR-04 | 1.2 | Y | PostGIS GEOGRAPHY(POINT, 4326) |

**Summary:** 35 of 42 requirements covered in Phases 1-8 plans. 7 deferred to Phases 9-11 (acceptable per scope). 1 requirement (THRS-04) is partially covered -- the enum placeholder exists but no implementation plan.

---

## Success Criteria Gaps

### Phase 1
| # | Criterion | Addressed | Issue |
|---|-----------|-----------|-------|
| 1 | Upload FIT from Garmin, see it imported | Yes | Plans 1.5, 1.6 |
| 2 | Second-by-second data in hypertables | Yes | Plan 1.2, 1.6 |
| 3 | Activity metadata in PostgreSQL | Yes | Plan 1.2 |
| 4 | Original FIT files preserved | Yes | Plan 1.6 |
| 5 | NUMERIC types for power | Yes | Plan 1.2, cross-phase chain |
| 6 | PostGIS GEOGRAPHY + correct distances | Yes | Plan 1.2, 1.10 |
| 7 | System runs via Docker Compose (PostgreSQL + TimescaleDB + Redis) | **CONTRADICTION** | See Issue #1 below |

### Phase 2
All 7 success criteria addressed. No gaps.

### Phase 3
All 4 success criteria addressed. No gaps.

### Phase 4
| # | Criterion | Addressed | Issue |
|---|-----------|-----------|-------|
| 4 | Xert model estimates threshold (dynamic, changes daily) | **NO** | THRS-04 has no Phase 4 plan. See Issue #2. |

All other Phase 4 criteria addressed.

### Phase 5-8
All success criteria addressed. No gaps.

---

## Issues

### Issue #1: Docker Compose Architecture Contradiction
**Severity:** HIGH
**Phase/Plan:** Phase 1 / Plan 1.3
**Problem:** ROADMAP.md Phase 1 Success Criterion #7 states "System runs via Docker Compose (PostgreSQL + TimescaleDB + Redis)." However, the PLANS.md key constraint (and 01-CONTEXT.md) explicitly state that "PostgreSQL + TimescaleDB + PostGIS runs on the user's NAS, NOT in Docker. Docker Compose runs the FastAPI app, Celery worker, and Redis only." Meanwhile, 01-CONTEXT.md says "All-in-one docker compose: app + DB (TimescaleDB + PostGIS) + Redis + Celery worker." There are three conflicting statements:
  - ROADMAP: Docker Compose includes PostgreSQL + TimescaleDB + Redis
  - PLANS.md: PostgreSQL on NAS, NOT in Docker
  - 01-CONTEXT.md: All-in-one docker compose INCLUDING DB

**Recommendation:** Resolve this contradiction before Phase 1 begins. The most flexible approach is to support BOTH: (a) a `docker-compose.yml` that includes the database for easy standalone deployment, and (b) an "external DB" config for NAS users. The plans currently only cover option (b). Either update the plan to include a DB-included compose profile, or update the ROADMAP and CONTEXT to match the plans.

### Issue #2: THRS-04 (Xert Threshold Model) Has No Implementation Plan
**Severity:** MEDIUM
**Phase/Plan:** Phase 4
**Problem:** THRS-04 requires "System estimates threshold using reverse-engineered Xert model (dynamic, changes daily)." This is listed in the Phase 4 ROADMAP success criteria (#4) and in the threshold method enum in Plan 4.1 (`xert_model`). However, no Phase 4 plan implements the Xert model threshold estimation. This is logically correct (Xert algorithms are Phase 9-10), but it means Phase 4 cannot satisfy its own success criterion #4.

**Recommendation:** Either (a) move THRS-04 out of Phase 4 into Phase 10 where Xert algorithms are built, updating the ROADMAP accordingly, or (b) add a stub plan in Phase 4 that implements the data model + placeholder, with the actual algorithm deferred. Option (a) is cleaner.

### Issue #3: NP Precision Claim vs. NumPy Float64 Reality
**Severity:** MEDIUM
**Phase/Plan:** Phase 2 / Plan 2.1
**Problem:** Plan 2.1 states "All calculations use Python Decimal or NumPy with sufficient precision, stored as NUMERIC." However, NumPy float64 is NOT equivalent to Python Decimal or PostgreSQL NUMERIC. Float64 has ~15-17 significant digits but still suffers from IEEE 754 representation errors. The cross-phase precision chain (line 1932) says "NP calculation uses NumPy with float64, result stored as NUMERIC," which is honest but contradicts the earlier claim of "Decimal or NumPy." The 4th-power operation in NP can amplify floating-point errors for high power values.

**Recommendation:** Clarify the precision strategy. Using NumPy float64 for intermediate calculations is practical and the error is negligible for cycling power data (worst case: sub-0.01W error). But the plan should explicitly state "NumPy float64 for computation performance, final results rounded and stored as NUMERIC" rather than implying Decimal arithmetic. Remove the misleading "Decimal or NumPy" phrasing.

### Issue #4: Celery Worker Using Sync SQLAlchemy but App Uses Async
**Severity:** LOW
**Phase/Plan:** Phase 1 / Plans 1.4, 1.6
**Problem:** The plan specifies the FastAPI app uses `async_sessionmaker` with `asyncpg`, while the Celery worker uses a sync SQLAlchemy engine. This is architecturally sound (Celery tasks are sync), but the plans never create the sync engine or sync session factory. Plan 1.2 only creates `create_async_engine`. The Celery worker code in Plan 1.6 says "Bulk insert using SQLAlchemy insert().values(rows) with sync engine in Celery worker" but no plan creates this sync engine.

**Recommendation:** Add explicit creation of a sync engine (`create_engine` with `psycopg2` driver) to Plan 1.2 or Plan 1.4. Add `psycopg2-binary` to dependencies in Plan 1.1.

### Issue #5: Missing Test FIT File Fixtures Strategy
**Severity:** LOW
**Phase/Plan:** Phase 1 / Plan 1.5
**Problem:** Plan 1.5 references "test FIT files (various Garmin devices)" in `backend/tests/fixtures/` but does not explain how these will be sourced. Real FIT files contain personal GPS data and cannot be committed to a public repo. Generating synthetic FIT files requires a FIT SDK or custom binary writer.

**Recommendation:** Plan should specify approach: (a) use Garmin FIT SDK to generate synthetic test files, (b) use a library like `fit_tool` to create minimal test FIT files, or (c) include anonymized real files with GPS data stripped/randomized. This affects the feasibility of automated CI testing.

### Issue #6: Phase 5 (Auth) After Phase 3-4 Creates Unprotected API Surface
**Severity:** MEDIUM
**Phase/Plan:** Phase 5 ordering
**Problem:** Phases 1-4 build fully functional API endpoints (upload, metrics, Strava OAuth, settings) with no authentication. Phase 5 then retrofits auth onto all existing endpoints. This means during Phases 1-4 development, there is no user scoping -- all data is implicitly "global." The Strava integration (Phase 3) stores encrypted OAuth tokens but has no user concept to associate them with. Plan 1.8 (Garmin) creates an `Integration` model with `user_id FK`, but there is no user table until Phase 5 creates the auth system. Wait -- the User model IS created in Plan 1.2 (migration 001). So the user table exists, but there is no auth mechanism to identify the current user.

**Recommendation:** This is acceptable for a single-developer project where auth is a "hardening" step, but the plans should acknowledge the gap. Add a note that Phases 1-4 assume a single hardcoded user_id (e.g., user_id=1 created via migration seed data or setup endpoint). Plan 1.2 creates the User model but no user is ever inserted until Phase 5. Add a seed user to migration 001 or Plan 1.1.

### Issue #7: No Error Monitoring or Logging Strategy
**Severity:** LOW
**Phase/Plan:** Cross-phase
**Problem:** No plan addresses structured logging, error tracking, or monitoring. For a self-hosted application processing background tasks (Celery), observability is important. Celery task failures, Garmin/Strava API errors, and FIT parse failures could go unnoticed.

**Recommendation:** Add a cross-phase concern for logging: structured JSON logging (e.g., `structlog`), Celery task error logging, and optionally a simple health dashboard showing recent task failures. This does not need its own phase -- it can be a requirement added to Plan 1.1 (add structlog dependency) and Plan 1.4 (structured task logging).

### Issue #8: Strava Webhook Requires Public URL
**Severity:** LOW
**Phase/Plan:** Phase 3 / Plan 3.3
**Problem:** Plan 3.3 acknowledges that "Webhook URL must be publicly accessible" and suggests ngrok for dev. However, the target deployment is a home server/NAS. Most home networks are behind NAT/CGNAT with no public IP. The plan does not address how the webhook URL will be made accessible in production.

**Recommendation:** Add a note on production webhook options: (a) dynamic DNS + port forwarding, (b) Cloudflare Tunnel, (c) fall back to polling-only sync (Plan 3.2 already supports manual/periodic sync). Option (c) means the webhook is a nice-to-have, not a hard requirement.

### Issue #9: Bulk Import Rate Limiting May Be Insufficient
**Severity:** LOW
**Phase/Plan:** Phase 1 / Plan 1.7
**Problem:** Plan 1.7 sets "max 10 concurrent parse tasks per batch" but does not explain the enforcement mechanism. Celery does not natively support per-batch concurrency limits. Additionally, bulk import of 1500+ FIT files (Garmin export) will generate 1500+ individual Celery tasks, which could overwhelm Redis memory if queued all at once.

**Recommendation:** Specify the concurrency control mechanism: (a) Celery `chord` with chunked groups, (b) a semaphore via Redis, or (c) iterative queuing (queue next N after previous N complete). Option (c) is simplest and recommended.

---

## Risk Assessment (Top 5)

### Risk 1: Unofficial Garmin API Breakage
**Phase:** 1 (Plan 1.8)
**Probability:** HIGH | **Impact:** MEDIUM
**Description:** The `garminconnect` Python library uses unofficial APIs that Garmin actively breaks. Session handling, 2FA enforcement, and CAPTCHA requirements change without notice. This is the primary data ingestion path for many users.
**Mitigation:** The plan already includes FIT file upload as a fallback. Add explicit degraded-mode handling: if Garmin sync fails, surface a clear error with instructions for manual export. Consider adding Garmin bulk export re-import as a one-click recovery option.

### Risk 2: TimescaleDB + PostGIS on External NAS Compatibility
**Phase:** 1 (Plan 1.2)
**Probability:** MEDIUM | **Impact:** HIGH
**Description:** Running TimescaleDB + PostGIS on a NAS (likely Synology/QNAP) with specific PostgreSQL versions may cause extension compatibility issues. TimescaleDB version pinning with asyncpg driver compatibility adds another dimension. The NAS may run an older PostgreSQL version that is incompatible with the required TimescaleDB features (compression policies, specific hypertable options).
**Mitigation:** Document minimum PostgreSQL version (14+), TimescaleDB version (2.11+), and PostGIS version (3.3+). Add a pre-flight check in the health endpoint that validates extension versions. Consider offering the Docker-included DB option (see Issue #1) as the primary path.

### Risk 3: Strava Rate Limiting During Historical Backfill
**Phase:** 3 (Plan 3.4)
**Probability:** MEDIUM | **Impact:** MEDIUM
**Description:** Backfilling 1500 activities from Strava requires ~3000 API calls (list + streams). At 200 req/15min, this takes ~3.75 hours minimum. Rate limit errors (429), token expiry during long backfill, and network interruptions could cause partial imports that are difficult to resume.
**Mitigation:** Plan 3.4 mentions resumable backfill ("tracks last processed page"), which is good. Ensure the implementation uses cursor-based pagination rather than page-number pagination (Strava returns `after` timestamps). Add a progress checkpoint every 50 activities.

### Risk 4: LTTB Downsampling Algorithm Correctness
**Phase:** 1 (Plan 1.10)
**Probability:** LOW | **Impact:** MEDIUM
**Description:** The LTTB (Largest Triangle Three Buckets) algorithm for stream downsampling is non-trivial to implement correctly. An incorrect implementation could distort power peaks or HR patterns in the summary view, leading to misleading charts.
**Mitigation:** Use an existing Python LTTB library (e.g., `lttbc` or `numpy-lttb`) rather than implementing from scratch. Add a test that verifies max/min values in the downsampled output match the full dataset.

### Risk 5: Multi-Method Metric Cache Storage Growth
**Phase:** 4 (Plan 4.4)
**Probability:** LOW | **Impact:** MEDIUM
**Description:** Pre-computing metrics for ALL threshold methods means 3x storage in activity_metrics and daily_fitness tables. With 1500+ activities and 7+ years of daily data, this could grow significantly. When Xert model is added (Phase 10), it becomes 4x. If additional methods are added, it scales linearly.
**Mitigation:** The plan acknowledges the 3x cost as "acceptable." This is correct for the initial scale. Add a monitoring note: track table sizes after Phase 4 and evaluate if compression or materialized views are needed for daily_fitness.

---

## Acceptance Criteria Quality Assessment

**Strong (testable, specific, measurable):**
- Plan 1.2: "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'activity_streams' returns 1 row" -- excellent
- Plan 2.4: "CTL after 42 days of 100 TSS/day ~ 63.2" -- mathematically verifiable
- Plan 1.6: "Duplicate upload returns 409 Conflict with existing activity_id" -- specific HTTP behavior

**Weak (vague or untestable):**
- Plan 2.1: "Test against known NP values from TrainingPeaks/intervals.icu reference" -- where are these reference values? Need specific test vectors.
- Plan 8.1: "Chart loads within 1 second (cached data)" -- performance criteria without a defined test environment are hard to enforce.
- Plan 1.10: "Response time < 500ms for 2-hour ride stream data" -- same issue, depends on hardware.
- Plan 6.5: "Build size reasonable (<2MB for initial load)" -- good threshold but Recharts + Leaflet + Zustand will likely push past 2MB. Verify this is achievable; 3-4MB may be more realistic.
- Plan 8.2: "Power curve for user with 100+ activities computes within 5 seconds" -- sliding-window computation over 100+ activities with 3600+ records each is computationally expensive. May need pre-computation, not just caching. The 5-second budget may be tight.

---

## Complexity Estimates Assessment

| Plan | Estimated | Critic Assessment | Notes |
|------|-----------|-------------------|-------|
| 1.1 | M | Agree | Standard scaffolding |
| 1.2 | L | Agree | Async SQLAlchemy + TimescaleDB + PostGIS + migrations is genuinely complex |
| 1.3 | M | Agree | Docker multi-service config |
| 1.4 | M | Agree | Celery setup is straightforward |
| 1.5 | L | Agree | FIT format parsing with device variability is complex |
| 1.6 | L | Agree | Full pipeline: upload -> store -> queue -> parse -> bulk insert |
| 1.7 | M | Agree | Zip handling + batch tracking |
| 1.8 | L | Agree | Unofficial API + encryption + periodic tasks |
| 1.9 | S | Agree | Simple CRUD + CSV parsing |
| 1.10 | M | Agree | LTTB + GeoJSON |
| 2.1 | M | **Slightly low** | Edge case handling for NP is subtle; should be M-L |
| 2.4 | L | Agree | EWMA with incremental updates and full rebuild |
| 4.4 | L | Agree | Multi-method caching is architecturally complex |
| 7.1 | L | Agree | Zone shading with Recharts ReferenceArea is non-trivial |
| 8.2 | L | **Slightly low** | Mean-max power computation across all activities is expensive. Should consider pre-computation strategy. |

Overall, complexity estimates are realistic. Two items may be slightly underestimated but not enough to be concerning.

---

## Phase 1 Context Incorporation

Checking each 01-CONTEXT.md decision against the plans:

| Context Decision | Plan Coverage | Status |
|-----------------|---------------|--------|
| Web UI drag-and-drop + API endpoint | Plan 6.3 (frontend), Plan 1.6 (API) | OK |
| Single file + zip + directory import | Plan 1.6 (single), Plan 1.7 (zip). **No directory import plan.** | **GAP** |
| Partial import on parse errors | Plan 1.5 (warnings list, partial data) | OK |
| Duplicate detection by fingerprint | Plan 1.6 (SHA256 + timestamp/device) | OK |
| Multiple devices same ride | Not addressed in any plan | **GAP** |
| Garmin bulk export archive | Plan 1.7 (zip archive support) | OK |
| Automated Garmin sync via garminconnect | Plan 1.8 | OK |
| Manual FIT upload as fallback | Plan 1.6 | OK |
| Health data (sleep, weight, HR, HRV) | Plan 1.8 (stored in health_metrics) | OK |
| Health data views deferred | Plan 1.8 explicitly defers | OK |
| Manual entry form | Plan 1.9 | OK |
| CSV import for bulk historical | Plan 1.9 | OK |
| Keep original FIT files | Plan 1.6 (permanent storage) | OK |
| Algorithm changes trigger reprocessing | Plan 2.3 (recompute_all_metrics) | OK |
| No metric versioning | Plan 2.3 ("Metrics are replaced on recomputation") | OK |
| 7+ years, 1500+ rides, chunk sizing | Plan 1.2 (90-day chunks) | OK |
| Xert data for validation only | Not addressed (Phases 9-10 deferred) | OK (deferred) |
| Docker: app + DB + Redis + Celery | **Contradicted** -- plans exclude DB from Docker | **ISSUE** (see Issue #1) |
| First-run setup wizard | Plan 5.3 (API), Plan 6.2 (frontend) | OK |
| Dev: Docker for services, Python local with uv | Plan 1.3 (docker-compose.dev.yml) | OK |
| Garmin sync frequency | Plan 1.8 (30-minute Celery Beat) | OK |
| Loading/progress UI for bulk imports | Plan 1.7 (batch status endpoint) | OK |
| FIT parse error detail | Plan 1.5 (warnings list) | OK |
| Chunk interval ~90 days | Plan 1.2 (INTERVAL '90 days') | OK |
| Celery queue priority | Plan 1.4 (high_priority, low_priority) | OK |

**Context gaps:**
1. **Directory import** -- 01-CONTEXT.md says "directory import (point at folder)" but no plan implements this. Only file upload and zip archive are planned.
2. **Multiple devices same ride** -- 01-CONTEXT.md says "Multiple devices can record the same ride -- summary stats only on one set of power/HR data." No plan addresses detecting or merging dual-recorded rides.

---

## Over/Under Engineering

### Potential Over-Engineering
1. **Multi-method metric pre-caching (Plan 4.4)**: Computing metrics for ALL methods on every import is forward-looking but expensive. Initially there are only 2-3 methods. Consider computing on-demand with caching rather than pre-computing all. However, the user requirement (THRS-07) explicitly demands "instant" switching, so this is justified.

2. **Nginx reverse proxy in Phase 1 (Plan 1.3)**: Adding Nginx in the initial Docker setup adds complexity. For a single-user self-hosted app, FastAPI can serve directly. Nginx becomes valuable only when the frontend is added in Phase 6. Consider deferring Nginx to Phase 6.

3. **Two-queue Celery priority system (Plan 1.4)**: high_priority and low_priority queues are a nice design but may be premature. A single queue with task priority could suffice initially.

### Potential Under-Engineering
1. **No database backup strategy**: For a self-hosted platform storing 7+ years of irreplaceable training data, there is no mention of backup procedures, pg_dump scheduling, or disaster recovery.

2. **No rate limiting on API endpoints**: No plan mentions API rate limiting. While this is a self-hosted app, a misbehaving client or integration could overwhelm the API.

3. **No frontend error boundary or error handling strategy**: Plans mention error states for individual components but no global error boundary, error reporting, or user-facing error recovery patterns.

4. **No migration rollback testing**: Plan 1.2 mentions rollback works, but no plan includes rollback testing as part of the CI/verification strategy for subsequent migrations.

5. **No WebSocket or SSE for real-time task progress**: Plans use polling (GET /tasks/{id}) for upload progress. For a modern UX, consider Server-Sent Events for real-time progress updates. This is a minor enhancement, not critical.

---

## Recommendations

### Critical (address before execution)
1. **Resolve Docker Compose contradiction** (Issue #1). Decide: DB in Docker or external. Update ROADMAP, CONTEXT, and PLANS to be consistent. Recommended: support both via Docker Compose profiles.

2. **Move THRS-04 to Phase 10** (Issue #2). The Xert threshold model cannot be implemented without Xert algorithms. Update Phase 4 ROADMAP success criteria to remove criterion #4, or rephrase it as "System architecture supports future Xert model integration."

3. **Add seed user for Phases 1-4** (Issue #6). Insert a default user in migration 001 or add a bootstrap endpoint so Phases 1-4 have a user_id to associate data with.

### Important (address during Phase 1)
4. **Add sync SQLAlchemy engine** (Issue #4). Create the sync engine and add psycopg2-binary to dependencies for Celery workers.

5. **Define test FIT file sourcing strategy** (Issue #5). Decide and document how test fixtures will be created.

6. **Add directory import plan** or explicitly defer it. 01-CONTEXT.md mentions it; either plan it or move it to backlog.

7. **Clarify NP precision approach** (Issue #3). State explicitly: "NumPy float64 for computation, results rounded to 1 decimal and stored as NUMERIC."

### Nice-to-Have (address when convenient)
8. Add structured logging (structlog) to Plan 1.1 dependencies.
9. Add database backup guidance as a cross-phase concern.
10. Consider SSE for task progress instead of polling.
11. Address multiple-device-same-ride scenario or defer explicitly to backlog.

---

*Review completed: 2026-02-10*
*Reviewer: Quality Critic (Opus)*
