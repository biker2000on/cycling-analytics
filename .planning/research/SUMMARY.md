# Project Research Summary

**Project:** Cycling Analytics Platform
**Domain:** Self-hosted cycling analytics with power-based training metrics
**Researched:** 2026-02-10
**Confidence:** HIGH

## Executive Summary

This is a self-hosted power-based cycling analytics platform competing against commercial SaaS solutions (intervals.icu, Xert, TrainingPeaks). The core value proposition is **accurate power-based fitness tracking with Xert algorithm precision** while maintaining privacy through self-hosting. Experts build these platforms using modular monolith architecture with specialized time-series databases, scientific computing libraries for power calculations, and chart-heavy dashboards for visualization.

The recommended approach is a **FastAPI + React + TimescaleDB stack** with modular monolith architecture. Start with core data import (FIT files, Strava), implement Coggan metrics first (CTL/ATL/TSB, TSS), then layer in Xert differentiation (XSS, threshold models) once the foundation is proven. Use TimescaleDB hypertables for second-by-second power data, continuous aggregates for dashboard performance, and background workers (Celery) for file parsing and metric computation.

The critical risk is **floating-point precision errors** breaking exact match validation against Xert's calculations. Mitigation requires using NUMERIC types for all power calculations, storing FTP at ride time (not current FTP), and implementing deterministic calculation order. Secondary risks include FIT parser device variability (use battle-tested library, not custom), TimescaleDB chunk misconfiguration (calculate proper chunk_time_interval upfront, not default), and Strava rate limit exhaustion (use webhooks, not polling).

## Key Findings

### Recommended Stack

The stack centers on modern Python async frameworks (FastAPI), scientific computing (NumPy/Pandas), time-series database optimization (TimescaleDB), and React-based charting (Recharts). All technologies are battle-tested in data-heavy analytics domains with strong 2026 support.

**Core technologies:**
- **FastAPI 0.128.0+**: REST API framework — 10-100x faster than Flask, async-first, native Pydantic validation, automatic OpenAPI docs. Ideal for data-heavy APIs with complex validation.
- **TimescaleDB 2.18.0+ (PostgreSQL 17)**: Time-series extension — 20x faster than vanilla PostgreSQL for time-series queries, automatic hypertables for second-by-second ride data, compression, continuous aggregates.
- **React 18.3+ with Vite 7.0+**: Frontend — largest ecosystem, best for complex dashboards, 390ms startup vs 4.5s for CRA. Recharts integrates natively for time-series charting.
- **SQLAlchemy 2.1+ with asyncpg**: ORM — async support, Data Mapper pattern for complex queries, explicit control over TimescaleDB features. Performance leader in benchmarks.
- **NumPy 2.2+ / Pandas 2.2+**: Scientific computing — foundation for power calculations, 20x faster than pure Python, standard for data analysis.
- **Celery with Redis**: Background workers — async processing for FIT parsing, Strava sync, metric computation. Essential for non-blocking API responses.
- **Recharts 3.3.0+**: Chart library — React-native, declarative API, excellent time-series support with Brush component for zoom/pan, lighter than Plotly (50KB vs 2MB+).
- **uv 0.5.0+**: Package manager — 10-100x faster than pip, single binary replaces pip/virtualenv/pyenv, global module cache.

**Avoid:**
- Create React App (unmaintained, 10x slower than Vite)
- Flask (no async-first, no auto-docs, slower)
- MongoDB/NoSQL (time-series data needs relational + hypertables)
- pip (10-100x slower than uv)

### Expected Features

Research shows clear feature tiers: table stakes expected by all users, differentiators for competitive advantage, and anti-features that seem good but create problems.

**Must have (table stakes):**
- Data import from Garmin/Strava — users need connectivity to major platforms
- Activity list/detail views — drill-down into rides expected
- Basic power metrics (TSS, IF, NP) — core Coggan metrics required
- CTL/ATL/TSB tracking — standard fitness tracking model
- Fitness chart (PMC) — visual representation of fitness progression
- Calendar view — weekly summaries expected
- Critical power curve — power users expect performance tracking
- Route map display — visual context for outdoor rides
- FTP/threshold configuration — required for any power analysis

**Should have (competitive):**
- Xert XSS metrics (Low/High/Peak) — advanced training load calculation, differentiator
- Xert threshold model — continuous threshold estimation without testing
- 30-second power zone shading — granular visualization, compute-intensive
- Fat/carb utilization calculation — metabolic insight rare in free platforms
- Block periodization planning — structured season planning
- Self-hosted/privacy-first — differentiates from cloud platforms
- Open algorithm implementation — transparency unlike proprietary platforms

**Defer (v2+):**
- Real-time live tracking — scope creep, rarely used
- Social feed/comments — moderation problem, not core value
- Workout recommendations AI — complex ML, high maintenance
- Mobile app — 2x development effort, responsive web sufficient for MVP
- Built-in workout player — requires device integration, many existing solutions

**Anti-features to avoid:**
- Real-time live tracking — requires websockets, scope creep
- Social features — becomes moderation problem
- Custom charts/dashboards — infinite feature requests, never "done"

### Architecture Approach

Modular monolith with clear internal boundaries: routers (API), services (business logic), workers (async processing), and models (data layer). TimescaleDB hypertables for high-frequency time-series data, continuous aggregates for pre-computed rollups, Redis for cache.

**Major components:**
1. **FastAPI Backend** — REST API with modular routers (auth, activities, metrics, streams, routes, integrations). Service layer isolates business logic from HTTP.
2. **Celery Workers** — Background processing for FIT parsing, Strava sync, metric computation. Priority queues (high/low) for user-facing vs background tasks.
3. **TimescaleDB Hypertables** — Second-by-second power/HR/cadence/GPS streams. Automatic time-based partitioning (chunk_time_interval = 90 days for 1Hz data), compression after 7 days (10-20x).
4. **Continuous Aggregates** — Pre-computed daily/weekly/monthly totals. Auto-refresh every hour. Massive dashboard speedup (10-100x).
5. **Redis Cache** — Computed CTL/ATL/TSB values (5 min TTL), critical power curves, session tokens.
6. **React SPA Frontend** — Dashboard charts (Recharts), activity detail views, route maps (Leaflet).

**Key architectural patterns:**
- **Hybrid Time-Series Schema**: Hypertables for streams (activity_streams), regular tables for metadata (activities, users, thresholds), continuous aggregates for rollups (daily_totals, weekly_fitness).
- **Background Job Processing**: Celery for operations >1 second (FIT parsing, Strava API, metric computation). Inline for fast operations (<100ms).
- **Database-Centric Caching**: TimescaleDB continuous aggregates for time-based rollups, Redis for frequently accessed computed metrics.
- **Multi-Method Threshold Management**: Store multiple FTP values per user (manual, auto-detected, lab-tested), compute metrics for all methods, let users switch views.

### Critical Pitfalls

The top pitfalls all relate to data precision, performance at scale, and integration complexity. Most are avoidable with proper foundation work but expensive to fix later.

1. **Floating-Point Precision Errors Breaking Exact Match Validation** — Accumulated rounding errors prevent exact match against Xert. Use NUMERIC types for all power calculations, store power as integers (watts × 1000), document precision requirements (TSS must match Xert within ±0.01). **Phase 1 critical — recovery cost HIGH (recalculate all historical data).**

2. **FIT File Device Variability Breaking Parser** — Manufacturer-specific extensions and variable field definitions cause failures. Use battle-tested library (python-fitparse), implement graceful degradation, test across device matrix (Edge 520/530/830/1030, Fenix 6/7), store original FIT for reprocessing. **Phase 1 critical — recovery cost MEDIUM (reprocess with improved parser).**

3. **TimescaleDB Chunk Size Misconfiguration Killing Performance** — Default 7-day chunks create thousands of tiny chunks for 1Hz data, causing query planning overhead. Calculate proper chunk_time_interval (aim for 25% RAM per chunk, ~90 days for 1Hz cycling data with 16GB RAM). **Phase 1 critical — recovery cost HIGH (recreate hypertable, hours of downtime).**

4. **Strava API Rate Limit Exhaustion Blocking Multi-User Sync** — Default limits (200/15min, 2000/day) shared across all users. Use webhooks instead of polling, implement exponential backoff on 429 errors, batch user syncs, cache activity metadata. **Phase 2 critical — recovery cost MEDIUM (implement webhooks, refactor sync logic).**

5. **Normalized Power Algorithm Edge Cases Creating Validation Failures** — Short rides (<10 min), dropouts (power = 0), extreme spikes (1500W sprints) break assumptions. Implement minimum duration check, handle zeros specially, apply spike detection, validate against Xert edge cases. **Phase 1 critical — recovery cost MEDIUM (recalculate NP for affected rides).**

6. **PostGIS Coordinate System Confusion Producing Wrong Distances** — Using GEOMETRY with lat/lon treats coordinates as flat plane. Use GEOGRAPHY type for GPS coordinates, always returns meters, document coordinate order (longitude first, latitude second). **Phase 1 critical — recovery cost HIGH (schema change, re-import all route data).**

7. **Dynamic FTP Threshold Causing Retroactive Metric Instability** — When FTP changes, historical TSS becomes invalid. Store ftp_at_ride_time with each ride, calculate TSS using historical FTP, track FTP history. **Phase 1 critical — recovery cost HIGH (backfill historical FTP, potentially estimate or invalidate old calculations).**

8. **Row-Level Security Performance Degradation With Data Growth** — RLS policies perform well initially but degrade catastrophically as data grows. Index policy columns (user_id, timestamp), keep policies simple, use EXPLAIN ANALYZE to verify index usage. **Phase 2 critical — recovery cost MEDIUM (add indexes, optimize queries).**

## Implications for Roadmap

Based on research, the project should follow a **foundation-first** approach with 3-4 core phases for MVP, then expansion phases for differentiation.

### Suggested Phase Structure

#### Phase 1: Data Foundation (Core Infrastructure + Import + Basic Metrics)
**Rationale:** All other work depends on correct data storage and calculation precision. Floating-point precision errors and chunk misconfiguration are expensive to fix later (HIGH recovery cost). TimescaleDB setup must be correct before any data import.

**Delivers:**
- Docker Compose setup (PostgreSQL + TimescaleDB + Redis)
- Database schema with proper types (NUMERIC for power, GEOGRAPHY for GPS)
- TimescaleDB hypertables with correct chunk_time_interval (90 days for 1Hz data)
- FIT file import with battle-tested parser (python-fitparse)
- Activity storage (metadata + streams in hypertable)
- Basic Coggan metrics (TSS, IF, NP with edge case handling)
- FTP management (manual entry, store ftp_at_ride_time)
- CTL/ATL/TSB calculation with proper time weighting

**Features from FEATURES.md:**
- Data Import (FIT files)
- Activity List/Table View
- Basic Power Metrics (TSS, IF, NP)
- FTP Configuration (Manual)
- Power Zones (7-zone Coggan)
- CTL/ATL/TSB Calculation

**Pitfalls avoided:**
- Floating-point precision errors (NUMERIC types, integer storage)
- FIT parser device variability (use python-fitparse, test device matrix)
- TimescaleDB chunk misconfiguration (calculate proper interval upfront)
- Normalized Power edge cases (minimum duration, zero handling, spike detection)
- PostGIS coordinate confusion (GEOGRAPHY type from start)
- Dynamic FTP instability (store ftp_at_ride_time)

**Research flags:** SKIP — well-documented patterns (TimescaleDB setup, FIT parsing, Coggan formulas)

---

#### Phase 2: API Integration + Multi-User
**Rationale:** Expands data sources to Strava (most popular) and establishes multi-user foundation. Strava rate limits require webhook architecture from start (MEDIUM recovery cost if polling used). RLS performance must be validated before launch.

**Delivers:**
- Strava OAuth2 integration
- Strava webhook subscriptions (push notifications)
- Rate limit tracking and exponential backoff
- Multi-user authentication (JWT)
- Row-level security policies with proper indexes
- Background worker queue prioritization (high/low)

**Features from FEATURES.md:**
- Data Import (Garmin + Strava)
- Single-User Auth (JWT)
- Multi-User + Data Isolation

**Stack from STACK.md:**
- FastAPI OAuth2 (built-in)
- PyJWT + passlib[bcrypt]
- Celery workers with priority queues
- stravalib 2.2+

**Pitfalls avoided:**
- Strava rate limit exhaustion (webhooks, not polling)
- Row-level security performance (index policy columns, test with 10+ users)

**Research flags:** POTENTIAL — Strava webhook implementation details, rate limit handling strategies. Likely needs `/gsd:research-phase` if team unfamiliar with OAuth2/webhooks.

---

#### Phase 3: Frontend Dashboard + Visualization
**Rationale:** First complete user experience. Users can import rides, view fitness progression, see activity detail. Depends on Phase 1 data foundation and Phase 2 authentication.

**Delivers:**
- React + Vite + TypeScript setup
- Authentication flow (login UI)
- Dashboard with fitness chart (Recharts: CTL/ATL/TSB)
- Activity list view (sortable, filterable)
- Activity detail view (timeline plot, basic stats)
- Route map display (Leaflet + OpenStreetMap)
- Calendar view with weekly summaries

**Features from FEATURES.md:**
- Dashboard/Fitness Chart (PMC)
- Activity List/Table View (UI)
- Activity Detail View
- Calendar View
- Route Map Display

**Stack from STACK.md:**
- React 18.3+ with Vite 7.0+
- Recharts 3.3.0+
- react-leaflet 4.x + Leaflet 1.9.4+
- TypeScript 5.7+

**Architecture component:**
- Frontend SPA (from ARCHITECTURE.md section: Frontend SPA → REST API → FastAPI Backend)

**Research flags:** SKIP — well-documented patterns (React + Recharts + Leaflet standard)

---

#### Phase 4: Advanced Analytics (Xert Differentiation)
**Rationale:** Implements competitive differentiators once core analytics proven. Xert algorithms require reverse-engineering (HIGH complexity), defer until foundation stable.

**Delivers:**
- Xert XSS metrics (Low/High/Peak)
- Xert threshold model (continuous estimation)
- 30-second power zone shading
- Critical power curve (1s-60min MMP)
- Power analysis detail (quartile analysis, variability index)
- Continuous aggregates for dashboard performance (daily_totals, weekly_fitness)
- Redis caching layer for computed metrics

**Features from FEATURES.md:**
- Xert XSS Metrics (Low/High/Peak)
- Xert Threshold Model
- 30-Second Power Zone Shading
- Critical Power Curve
- Power Analysis Detail

**Architecture component:**
- Continuous Aggregates (from ARCHITECTURE.md section: Continuous Aggregates for pre-computed rollups)
- Redis Cache (from ARCHITECTURE.md section: Fast cache for computed metrics)

**Pitfalls avoided:**
- None new, but validates Phase 1 precision work (Xert exact match requires NUMERIC types)

**Research flags:** REQUIRED — Xert algorithm reverse-engineering, continuous aggregate optimization. MUST use `/gsd:research-phase` for Xert XSS calculation details.

---

### Phase Ordering Rationale

**Why this order:**
1. **Data Foundation First:** Floating-point precision, chunk configuration, and FTP tracking are HIGH recovery cost if wrong. Fix before any data import.
2. **Integration Second:** Strava webhooks avoid rate limit exhaustion. Multi-user RLS must be validated before scale.
3. **Frontend Third:** First complete user experience. Can't demo until backend + frontend integrated.
4. **Differentiation Fourth:** Xert features are HIGH complexity, defer until core analytics proven stable.

**Why this grouping:**
- Phase 1 groups all schema/precision/calculation foundation (prevent expensive migrations)
- Phase 2 groups all external API integration (shared rate limit concerns)
- Phase 3 groups all frontend/visualization (shared React/charting patterns)
- Phase 4 groups all advanced analytics (shared Xert algorithm complexity)

**How this avoids pitfalls:**
- Phase 1 addresses 6 of 8 critical pitfalls (floating-point, FIT parser, TimescaleDB, NP edge cases, PostGIS, FTP stability)
- Phase 2 addresses 2 of 8 (Strava rate limits, RLS performance)
- Phase 3 has no new pitfalls (standard patterns)
- Phase 4 validates Phase 1 precision work (Xert exact match)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2: API Integration** — Strava webhook implementation, OAuth2 PKCE flow, rate limit strategies. Likely needs `/gsd:research-phase` if unfamiliar with webhooks.
- **Phase 4: Advanced Analytics** — Xert algorithm reverse-engineering (XSS calculation, threshold model), continuous aggregate optimization. MUST use `/gsd:research-phase` for Xert specifics.

**Phases with standard patterns (skip research-phase):**
- **Phase 1: Data Foundation** — TimescaleDB hypertable setup, FIT parsing with python-fitparse, Coggan CTL/ATL/TSB formulas all well-documented.
- **Phase 3: Frontend Dashboard** — React + Vite + Recharts + Leaflet standard patterns, extensive documentation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | FastAPI, SQLAlchemy, Recharts, Vite, TimescaleDB verified via Context7 official docs. uv, pytest verified via 2026 sources. NumPy/Pandas industry standard. |
| Features | HIGH | Verified against official intervals.icu, Xert, TrainingPeaks docs. Feature prioritization informed by competitor analysis and user forums. |
| Architecture | HIGH | TimescaleDB hypertable patterns verified via official docs. Modular monolith and background job processing backed by multiple sources. FIT parsing and Celery patterns industry standard. |
| Pitfalls | HIGH | Floating-point precision issues documented in official Python/PostgreSQL docs. TimescaleDB chunk sizing from official best practices. Strava rate limits from official API docs. PostGIS GEOGRAPHY vs GEOMETRY from official PostGIS docs. |

**Overall confidence:** HIGH

All core technologies verified through official documentation or Context7. Architecture patterns backed by multiple authoritative sources. Pitfalls derived from official documentation and domain-specific sources (TrainingPeaks, Strava Developer docs).

### Gaps to Address

**Xert algorithm specifics:** Research identified Xert XSS as key differentiator but couldn't access proprietary algorithm details. During Phase 4 planning, must use `/gsd:research-phase` to reverse-engineer from public Xert resources, user forums, or open-source implementations.

**FTP auto-detection methods:** Research confirmed multiple methods exist (95% 20min, 90% 8min, Xert model) but didn't detail implementation. During Phase 1, validate formulas against TrainingPeaks documentation and test cases.

**TimescaleDB chunk_time_interval calculation:** Research provided formula (25% RAM per chunk) but must validate during Phase 1 with actual data profile. Monitor chunk count and query planning time as data grows.

**Strava webhook signature verification:** Research confirmed webhooks required but didn't detail signature algorithm. During Phase 2 planning, reference official Strava webhook documentation for HMAC-SHA256 verification.

**PostGIS coordinate order edge cases:** Research warned "longitude first, latitude second" but didn't cover all FIT file coordinate formats. During Phase 1, validate against multiple FIT file samples to confirm coordinate extraction order.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` — FastAPI official documentation, version 0.128.0, async support verified
- Context7 `/websites/sqlalchemy_en_21` — SQLAlchemy 2.1 documentation, async support, PostgreSQL compatibility
- Context7 `/recharts/recharts` — Recharts v3.3.0 documentation, time-series features, Brush component
- Context7 `/vitejs/vite` — Vite v7.0.0 documentation, React plugin, performance benchmarks
- Context7 `/websites/react-leaflet_js` — react-leaflet v4.x documentation, React 18 compatibility
- Docker Hub `timescale/timescaledb:2.18.0-pg17` — TimescaleDB official images verified
- Strava Developers `/docs/rate-limits` — Official rate limit documentation (200/15min, 2000/day)
- TrainingPeaks Help Center — Official Coggan formula documentation (TSS, NP, CTL/ATL/TSB)
- PostGIS Documentation — GEOGRAPHY vs GEOMETRY type comparison, ST_Transform usage

### Secondary (MEDIUM confidence)
- JetBrains PyCharm Blog: FastAPI vs Django vs Flask (Feb 2025) — Performance benchmarks
- Stravalib Documentation `v2.2` — Official Strava API client library
- PyPI `fitparse 1.2.0+` — FIT file parser library verification
- intervals.icu Forum — Feature comparison, power curve implementation details
- Xert Baron Biosys — XSS calculation methodology, fitness signature explanation
- GitHub `python-fitparse`, `stravalib`, `timescaledb` — Repository verification, issue tracking

### Tertiary (LOW confidence)
- Self-hosted fitness platform comparisons — Market positioning insights (endurain, FitTrackee)
- Medium articles on floating-point precision, Celery patterns — Implementation examples (needs validation)

---
*Research completed: 2026-02-10*
*Ready for roadmap: yes*
