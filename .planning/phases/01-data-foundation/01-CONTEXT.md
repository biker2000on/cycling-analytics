# Phase 1: Data Foundation - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Core infrastructure for the cycling analytics platform: Docker Compose setup with TimescaleDB + PostGIS + Redis, FIT file import pipeline, Garmin Connect automated sync, data storage with numerical precision guarantees, and manual/CSV entry for pre-GPS historical rides. This phase establishes the data layer that all analytics and visualization phases build on.

</domain>

<decisions>
## Implementation Decisions

### FIT File Import Workflow
- Web UI (drag-and-drop/file picker) AND API endpoint for scripted imports
- Support single file upload, zip archive upload, and directory import (point at folder)
- Partial import on parse errors — import what's available, flag issues with warnings, never silently lose data
- Duplicate detection by fingerprinting rides (timestamp + device) — detect and skip automatically
- Multiple devices can record the same ride — summary stats only on one set of power/HR data
- Accept Garmin bulk data export archive for historical backfill

### Garmin Connect Data Pull
- Automated sync using unofficial garminconnect library (user accepts breakage risk)
- Also support manual FIT file export + upload as fallback
- Accept Garmin data export archive for initial historical backfill
- Pull both activity FIT files AND health data (sleep, weight, resting HR, HRV)
- Health data stored for future wellness features — views/analysis deferred to later phases

### Pre-GPS / Manual Activity Entry
- Manual entry form in web UI for rides without FIT files
- CSV import for bulk historical data
- API endpoint for scripted import
- Fields: date, duration, distance, average power, average HR, elevation gain, notes/description
- No second-by-second data for these — summary stats only

### Data Retention & Reprocessing
- Keep original FIT files for reprocessing
- Algorithm changes trigger auto-reprocessing of ALL historical rides (background job)
- Latest calculation replaces old values — no metric versioning
- Data volume: 7+ years, 1500+ rides with 1Hz data — TimescaleDB chunk sizing must account for this
- Xert data is for validation/reverse engineering ONLY — NOT stored in production database, test fixtures only

### Docker Deployment
- Target: home server / NAS
- All-in-one docker compose: app + DB (TimescaleDB + PostGIS) + Redis + Celery worker
- First run: config file for basics (DB credentials, secrets), web-based setup wizard for user account creation and Garmin/Strava connection
- Dev environment: Docker for services (DB, Redis), Python app runs locally with uv for faster iteration

### Claude's Discretion
- Garmin sync frequency (polling interval for automated sync)
- Loading/progress UI for bulk imports
- FIT parse error detail level and reporting format
- Exact chunk_time_interval calculation for TimescaleDB (research recommends ~90 days for 1Hz data with 7+ years)
- Celery worker configuration and queue priority design

</decisions>

<specifics>
## Specific Ideas

- Garmin Connect unofficial API via garminconnect Python library — user is comfortable with breakage risk
- Health data from Garmin (sleep, weight, HRV, resting HR) should be pulled and stored even though views aren't built yet
- Multiple devices recording the same ride is a real scenario — need to handle gracefully
- Pre-GPS rides go back many years — CSV import is critical for historical archive
- Xert data pulled separately only for algorithm validation, never mixed into production data

</specifics>

<deferred>
## Deferred Ideas

- Multi-device ride comparison (overlay data from multiple devices recording same ride) — add to roadmap backlog
- Health/wellness data views and analysis (sleep trends, weight tracking, HRV) — future phase
- Garmin health metrics integration with fitness tracking (e.g., HRV vs CTL correlation) — future phase

</deferred>

---

*Phase: 01-data-foundation*
*Context gathered: 2026-02-10*
