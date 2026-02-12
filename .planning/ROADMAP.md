# Roadmap: Cycling Analytics

## Overview

This roadmap delivers a self-hosted cycling analytics platform from data foundation through advanced Xert algorithm implementation. The journey progresses through four major arcs: establishing reliable data import and storage with precision guarantees (Phases 1-2), expanding data sources and enabling multi-user access (Phases 3-5), building the complete frontend experience with rich visualizations (Phases 6-8), and implementing competitive differentiation through Xert reverse-engineering and planning features (Phases 9-11). Each phase delivers verifiable user capabilities that build toward the core value: accurate power-based fitness tracking with Xert algorithm precision.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Foundation** - Core infrastructure with TimescaleDB, FIT import, precision storage
- [ ] **Phase 2: Coggan Metrics Engine** - TSS, NP, CTL/ATL/TSB, power zones
- [ ] **Phase 3: Strava Integration** - OAuth2, webhooks, activity sync
- [ ] **Phase 4: Threshold Management** - Multi-method FTP estimation with instant view switching
- [ ] **Phase 5: Multi-User Infrastructure** - Authentication, profiles, data isolation
- [ ] **Phase 6: Frontend Foundation** - React SPA, activity list/detail
- [ ] **Phase 7: Activity Detail Views** - Power analysis, HR analysis, route maps, zone shading
- [ ] **Phase 8: Dashboard & Charts** - Fitness tracker, critical power, calendar, totals
- [ ] **Phase 9: Xert Algorithm Core** - XSS Low/High/Peak strain calculations
- [ ] **Phase 10: Xert Advanced Features** - Dynamic threshold model, metabolic calculations, validation
- [ ] **Phase 11: Season Planning** - Block periodization, goal-based CTL progression

## Phase Details

### Phase 1: Data Foundation
**Goal**: User can import FIT files and store ride data with numerical precision in TimescaleDB hypertables
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-03, DATA-04, DATA-05, INFR-02, INFR-03, INFR-04
**Success Criteria** (what must be TRUE):
  1. User can upload a FIT file from Garmin Connect and see it imported
  2. Second-by-second power, HR, cadence, and GPS data is stored in TimescaleDB hypertables
  3. Activity metadata (date, duration, distance) is stored in PostgreSQL tables
  4. Original FIT files are preserved for reprocessing
  5. All power calculations use NUMERIC types (no floating-point errors)
  6. GPS coordinates use PostGIS GEOGRAPHY type and return correct distances
  7. System runs via Docker Compose (app + Redis + Celery worker, with optional included PostgreSQL + TimescaleDB or connection to external database)
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 2: Coggan Metrics Engine
**Goal**: User sees accurate TSS, NP, CTL/ATL/TSB calculations for every ride
**Depends on**: Phase 1
**Requirements**: METR-01, METR-02, METR-03, METR-04, METR-05, METR-06, METR-07
**Success Criteria** (what must be TRUE):
  1. User can view Normalized Power for any activity with edge case handling (short rides, dropouts, spikes)
  2. User can see Intensity Factor relative to their configured threshold
  3. User can see Training Stress Score (TSS) for every ride
  4. User can view CTL (42-day chronic training load) progression over time
  5. User can view ATL (7-day acute training load) progression over time
  6. User can view TSB (training stress balance = CTL - ATL) to assess readiness
  7. Power zones (7-zone Coggan model) are applied consistently based on threshold
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 3: Strava Integration
**Goal**: User can connect Strava account and automatically import activities via webhooks
**Depends on**: Phase 2
**Requirements**: DATA-02
**Success Criteria** (what must be TRUE):
  1. User can authenticate with Strava via OAuth2
  2. New Strava activities automatically appear in the system within 5 minutes
  3. System respects Strava rate limits (200/15min, 2000/day) with exponential backoff
  4. User can manually trigger re-sync for historical activities
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 4: Threshold Management
**Goal**: User can configure threshold estimation method and switch between views instantly
**Depends on**: Phase 2
**Requirements**: THRS-01, THRS-02, THRS-03, THRS-05, THRS-06, THRS-07, THRS-08 (THRS-04 deferred to Phase 10 -- Xert threshold model requires Xert algorithms from Phase 9)
**Success Criteria** (what must be TRUE):
  1. User can manually set FTP/threshold value
  2. System calculates threshold as 95% of 20-minute best effort
  3. System calculates threshold as 90% of 8-minute best effort
  4. User can select active estimation method in profile settings
  5. Switching threshold method shows results instantly (pre-cached for all methods)
  6. Historical threshold-at-ride-time is stored with each activity for accurate retrospective analysis
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 5: Multi-User Infrastructure
**Goal**: Multiple users can securely access their own data with authentication
**Depends on**: Phase 1
**Requirements**: INFR-01
**Success Criteria** (what must be TRUE):
  1. User can create an account and log in
  2. User can only access their own rides and metrics
  3. User profile stores threshold preferences and configuration
  4. Session tokens expire appropriately and support logout
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 6: Frontend Foundation
**Goal**: User can access web interface, view activity list, and drill into basic activity details
**Depends on**: Phase 5
**Requirements**: ACTV-01, ACTV-02
**Success Criteria** (what must be TRUE):
  1. User can log in via web interface
  2. User can view activity list sorted by date, distance, duration, or TSS
  3. User can click an activity to see detail page
  4. Activity detail shows timeline plot with power data
  5. React SPA loads quickly (<2 seconds) with Vite
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 7: Activity Detail Views
**Goal**: User can analyze activity with power zones, HR data, and route map
**Depends on**: Phase 6
**Requirements**: ACTV-03, ACTV-04, ACTV-05, ACTV-06
**Success Criteria** (what must be TRUE):
  1. Activity timeline shows 30-second power zone shading based on configured threshold method
  2. User can view power analysis page (quartile distribution, variability index, peak efforts)
  3. User can view heart rate analysis page with HR zones
  4. User can view route map for outdoor rides using OpenStreetMap + Leaflet
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 8: Dashboard & Charts
**Goal**: User can visualize fitness progression, critical power, and training calendar
**Depends on**: Phase 6
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. User can view fitness tracker chart (CTL/ATL/TSB over time) with date range selection
  2. User can view critical power curve showing best efforts over standard durations (5s, 1min, 5min, 20min, 60min)
  3. User can view training calendar (Monday first, configurable start day)
  4. Calendar shows weekly summary stats (total TSS, duration, distance)
  5. User can view totals page with aggregated charts (weekly/monthly/yearly trends)
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 9: Xert Algorithm Core
**Goal**: User sees Xert XSS strain scores (Low/High/Peak) matching Xert's exact calculations
**Depends on**: Phase 2
**Requirements**: XERT-01, XERT-02, XERT-03
**Success Criteria** (what must be TRUE):
  1. System calculates XSS Low strain score matching Xert output exactly
  2. System calculates XSS High strain score matching Xert output exactly
  3. System calculates XSS Peak strain score matching Xert output exactly
  4. XSS calculations handle edge cases (short intervals, high variability, endurance rides)
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 10: Xert Advanced Features
**Goal**: User sees dynamic threshold and metabolic calculations matching Xert exactly
**Depends on**: Phase 9
**Requirements**: XERT-04, XERT-05, XERT-06, XERT-07, THRS-04 (deferred from Phase 4 -- requires Xert algorithm core from Phase 9)
**Success Criteria** (what must be TRUE):
  1. System calculates threshold power, high intensity energy, peak power, and lower threshold power matching Xert exactly
  2. System calculates fat expenditure in grams based solely on power output, matching Xert exactly
  3. System calculates carb expenditure in grams based solely on power output, matching Xert exactly
  4. All Xert calculations validated to exact match against active Xert account data (validation test suite passing)
  5. System estimates threshold using reverse-engineered Xert model (dynamic, changes daily) -- satisfies THRS-04
**Plans**: TBD

Plans:
- [ ] TBD during planning

### Phase 11: Season Planning
**Goal**: User can define training blocks and generate CTL progression plans to reach target fitness
**Depends on**: Phase 8
**Requirements**: PLAN-01, PLAN-02, PLAN-03
**Success Criteria** (what must be TRUE):
  1. User can define training blocks (base, build, peak, recovery) with target CTL ramp rates
  2. User can set target event date and target fitness level
  3. System auto-generates CTL progression plan showing weekly TSS targets to reach goal by event date
**Plans**: TBD

Plans:
- [ ] TBD during planning

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Foundation | 10/10 | Complete | 2026-02-12 |
| 2. Coggan Metrics Engine | 0/TBD | Not started | - |
| 3. Strava Integration | 0/TBD | Not started | - |
| 4. Threshold Management | 0/TBD | Not started | - |
| 5. Multi-User Infrastructure | 0/TBD | Not started | - |
| 6. Frontend Foundation | 0/TBD | Not started | - |
| 7. Activity Detail Views | 0/TBD | Not started | - |
| 8. Dashboard & Charts | 0/TBD | Not started | - |
| 9. Xert Algorithm Core | 0/TBD | Not started | - |
| 10. Xert Advanced Features | 0/TBD | Not started | - |
| 11. Season Planning | 0/TBD | Not started | - |
