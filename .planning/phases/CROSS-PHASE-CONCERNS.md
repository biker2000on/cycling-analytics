
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
