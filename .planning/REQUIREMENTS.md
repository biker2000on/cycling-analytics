# Requirements: Cycling Analytics

**Defined:** 2026-02-10
**Core Value:** Accurate power-based fitness tracking (CTL/ATL/TSB) with reverse-engineered Xert algorithm precision

## v1 Requirements

### Data Import & Storage

- [ ] **DATA-01**: User can import ride data from Garmin Connect (FIT files)
- [ ] **DATA-02**: User can import ride data from Strava API (OAuth + webhooks)
- [ ] **DATA-03**: System stores second-by-second ride data (power, HR, cadence, GPS) in TimescaleDB hypertables
- [ ] **DATA-04**: System stores activity metadata (date, duration, distance, type) in standard PostgreSQL tables
- [ ] **DATA-05**: System stores original FIT files for reprocessing

### Core Metrics (Coggan)

- [ ] **METR-01**: System calculates Normalized Power (NP) with edge case handling (short rides, dropouts, spikes)
- [ ] **METR-02**: System calculates Intensity Factor (IF) relative to configured threshold
- [ ] **METR-03**: System calculates Training Stress Score (TSS)
- [ ] **METR-04**: System calculates CTL (42-day chronic training load)
- [ ] **METR-05**: System calculates ATL (7-day acute training load)
- [ ] **METR-06**: System calculates TSB (training stress balance = CTL - ATL)
- [ ] **METR-07**: System applies 7-zone Coggan power zones based on configured threshold

### Xert Reverse Engineering

- [ ] **XERT-01**: System calculates XSS Low strain score matching Xert's output exactly
- [ ] **XERT-02**: System calculates XSS High strain score matching Xert's output exactly
- [ ] **XERT-03**: System calculates XSS Peak strain score matching Xert's output exactly
- [ ] **XERT-04**: System calculates threshold power / high intensity energy / peak power / lower threshold power matching Xert exactly
- [ ] **XERT-05**: System calculates fat expenditure in grams based solely on power output, matching Xert exactly
- [ ] **XERT-06**: System calculates carb expenditure in grams based solely on power output, matching Xert exactly
- [ ] **XERT-07**: All Xert calculations validated to exact match against active Xert account data

### Threshold Configuration

- [ ] **THRS-01**: User can manually set FTP/threshold value
- [ ] **THRS-02**: System estimates threshold as 95% of 20-minute best effort
- [ ] **THRS-03**: System estimates threshold as 90% of 8-minute best effort
- [ ] **THRS-04**: System estimates threshold using reverse-engineered Xert model (dynamic, changes daily)
- [ ] **THRS-05**: User can select which estimation method is active in their profile
- [ ] **THRS-06**: System pre-computes and caches metrics for ALL threshold methods
- [ ] **THRS-07**: Switching threshold method shows pre-cached results instantly (no recalculation)
- [ ] **THRS-08**: System stores historical threshold-at-ride-time for each activity

### Activity Views

- [ ] **ACTV-01**: User can view activity list in table format (sortable by date, distance, duration, TSS)
- [ ] **ACTV-02**: User can view activity detail with timeline plot
- [ ] **ACTV-03**: Activity timeline shows 30-second shading based on Coggan power zones (threshold from configured method, dynamic per day)
- [ ] **ACTV-04**: User can view power analysis detail page for an activity
- [ ] **ACTV-05**: User can view heart rate analysis detail page for an activity
- [ ] **ACTV-06**: User can view route map for an activity (OpenStreetMap + Leaflet)

### Dashboard & Charts

- [ ] **DASH-01**: User can view fitness tracker chart (CTL/ATL/TSB over time with date range selection)
- [ ] **DASH-02**: User can view critical power curve (best efforts over standard durations)
- [ ] **DASH-03**: User can view calendar of training (Monday first, configurable start day)
- [ ] **DASH-04**: Calendar shows weekly summary stats (TSS, duration, distance)
- [ ] **DASH-05**: User can view totals page with charts (weekly/monthly/yearly aggregations)

### Season Planning

- [ ] **PLAN-01**: User can define training blocks (base, build, peak, recovery) with target CTL ramp rates
- [ ] **PLAN-02**: User can set a target event date and target fitness level
- [ ] **PLAN-03**: System auto-generates CTL progression plan to reach target fitness by event date

### Infrastructure

- [ ] **INFR-01**: Multi-user support with user profiles and authentication
- [ ] **INFR-02**: Self-hosted deployment via Docker
- [ ] **INFR-03**: All power calculations use NUMERIC types (not floating-point) for precision
- [ ] **INFR-04**: PostGIS GEOGRAPHY type for GPS coordinate storage

## v2 Requirements

### Advanced Analytics

- **V2-01**: Automatic interval detection (identify workout structure without manual laps)
- **V2-02**: Advanced CP modeling (Morton 3-parameter, Monod-Scherrer 2-parameter)
- **V2-03**: Activity comparison (side-by-side ride comparison for progression)

## Out of Scope

| Feature | Reason |
|---------|--------|
| SaaS / hosted service | Self-hosted by design, data ownership is core principle |
| Mobile app | Web-first, responsive design covers 90% of mobile needs |
| Social features | Not core value, creates moderation burden |
| Real-time live tracking | Post-ride analysis only, scope creep |
| Workout player | Requires device integration, many existing solutions |
| Nutrition tracking | Fat/carb from power data sufficient, don't track meals |
| Custom dashboards | Curated opinionated views, infinite feature requests |
| AI workout recommendations | Complex ML, high maintenance, Xert/TrainerRoad territory |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| METR-01 | Phase 2 | Pending |
| METR-02 | Phase 2 | Pending |
| METR-03 | Phase 2 | Pending |
| METR-04 | Phase 2 | Pending |
| METR-05 | Phase 2 | Pending |
| METR-06 | Phase 2 | Pending |
| METR-07 | Phase 2 | Pending |
| XERT-01 | Phase 9 | Pending |
| XERT-02 | Phase 9 | Pending |
| XERT-03 | Phase 9 | Pending |
| XERT-04 | Phase 10 | Pending |
| XERT-05 | Phase 10 | Pending |
| XERT-06 | Phase 10 | Pending |
| XERT-07 | Phase 10 | Pending |
| THRS-01 | Phase 4 | Pending |
| THRS-02 | Phase 4 | Pending |
| THRS-03 | Phase 4 | Pending |
| THRS-04 | Phase 4 | Pending |
| THRS-05 | Phase 4 | Pending |
| THRS-06 | Phase 4 | Pending |
| THRS-07 | Phase 4 | Pending |
| THRS-08 | Phase 4 | Pending |
| ACTV-01 | Phase 6 | Pending |
| ACTV-02 | Phase 6 | Pending |
| ACTV-03 | Phase 7 | Pending |
| ACTV-04 | Phase 7 | Pending |
| ACTV-05 | Phase 7 | Pending |
| ACTV-06 | Phase 7 | Pending |
| DASH-01 | Phase 8 | Pending |
| DASH-02 | Phase 8 | Pending |
| DASH-03 | Phase 8 | Pending |
| DASH-04 | Phase 8 | Pending |
| DASH-05 | Phase 8 | Pending |
| PLAN-01 | Phase 11 | Pending |
| PLAN-02 | Phase 11 | Pending |
| PLAN-03 | Phase 11 | Pending |
| INFR-01 | Phase 5 | Pending |
| INFR-02 | Phase 1 | Pending |
| INFR-03 | Phase 1 | Pending |
| INFR-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 42 total
- Mapped to phases: 42
- Unmapped: 0

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-10 after roadmap creation*
