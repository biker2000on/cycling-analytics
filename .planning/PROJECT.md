# Cycling Analytics

## What This Is

A self-hosted cycling analytics platform that imports ride data from Garmin and Strava, computes power-based performance metrics using reverse-engineered Xert algorithms and Coggan's training model, and provides intervals.icu-quality views for activity analysis, fitness tracking, and season planning. Designed for cyclists who want to own their data — deployable by anyone, not a SaaS product.

## Core Value

Accurate power-based fitness tracking (CTL/ATL/TSB) with reverse-engineered Xert algorithm precision — the daily pulse check that tells you where your fitness is and where it's heading.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Import ride data from Garmin Connect (FIT files)
- [ ] Import ride data from Strava API
- [ ] Store second-by-second ride data (power, HR, cadence, GPS) in TimescaleDB hypertables
- [ ] Reverse engineer Xert's XSS calculation (low, high, peak strain scores)
- [ ] Reverse engineer Xert's threshold power / high intensity energy / peak power / lower threshold power
- [ ] Reverse engineer Xert's fat and carb expenditure calculation (power-based)
- [ ] Validate all Xert reverse-engineered calculations to exact match against active Xert account data
- [ ] Implement Coggan's CTL (Chronic Training Load) calculation
- [ ] Implement Coggan's ATL (Acute Training Load) calculation
- [ ] Implement Coggan's TSB (Training Stress Balance) calculation
- [ ] Cache/store all computed metrics in the database
- [ ] Configurable threshold estimation method (95% of 20min, 90% of 8min, manual, Xert model)
- [ ] Threshold is dynamic per day (not static) when using Xert model
- [ ] Calculate normalized power, estimated power, XSS, TSS based on configured threshold method
- [ ] Cache results for all threshold estimation methods (view switches based on user config)
- [ ] Calendar view of training (Monday first, configurable start day) with weekly summary stats
- [ ] Table view of activities
- [ ] Fitness tracker chart (CTL/ATL/TSB over time)
- [ ] Critical power chart
- [ ] Totals page and chart
- [ ] Activity detail: timeline plot with 30s shading based on Coggan power zones (threshold from configured method)
- [ ] Activity detail: power analysis page
- [ ] Activity detail: heart rate analysis page
- [ ] Activity detail: route map using OpenStreetMap + Leaflet
- [ ] Season planning with block periodization (base, build, peak, recovery)
- [ ] Goal-based plan generation (target event date + target fitness, auto-generate CTL progression)
- [ ] Multi-user support with user profiles
- [ ] User authentication

### Out of Scope

- SaaS / hosted service — this is self-hosted only, by design
- Mobile app — web-first
- Social features (following, sharing) — personal analytics tool
- Real-time live tracking — post-ride analysis only
- Workout creation / structured workout player — this is analysis and planning, not execution

## Context

- Primary user is an experienced cyclist with deep knowledge of power-based training metrics
- Active Xert account available for algorithm validation — can pull activity tables to compare calculations
- intervals.icu is the UI/UX reference for charts and views (credentials in .env for reference access)
- All Xert calculations are based solely on power output (confirmed via their research and podcasts)
- Xert's threshold is dynamic (changes daily based on training history), not a static FTP value
- The application must support multiple threshold estimation methods with the ability to switch views between them
- Computed metrics should be pre-cached for all methods so switching is instant

## Constraints

- **Backend**: Python — preferred language for data/analytics work
- **Package Management**: uv — all Python tooling (packages, venvs, scripts)
- **Database**: PostgreSQL with TimescaleDB (hypertables for second-by-second data) and PostGIS (geospatial route data)
- **Standard Tables**: Normal PostgreSQL tables for users, activities, computed metrics, plans, configuration
- **Maps**: OpenStreetMap + Leaflet for route visualization
- **Deployment**: Self-hosted — must be easy to deploy (Docker likely)
- **Algorithm Accuracy**: Xert reverse engineering must achieve exact match against Xert's own calculations
- **Tech Stack**: Must be approved before development begins (frontend framework TBD during research)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PostgreSQL over MongoDB | Relational data model, aggregation-heavy analytics workload, JSONB for flexible parts | -- Pending |
| TimescaleDB for time-series | Second-by-second ride data is classic time-series; hypertables handle this efficiently | -- Pending |
| PostGIS for geospatial | Route data with GPS coordinates, map rendering with Leaflet | -- Pending |
| Python backend | User preference, strong for data/analytics domain | -- Pending |
| uv for Python tooling | Modern, fast package management | -- Pending |
| Cache all threshold methods | Pre-compute metrics for every estimation method so view switching is instant | -- Pending |
| Dynamic threshold (Xert model) | Threshold changes daily based on training history, not a static FTP | -- Pending |
| Self-hosted, not SaaS | Data ownership is a core principle | -- Pending |

---
*Last updated: 2026-02-10 after initialization*
