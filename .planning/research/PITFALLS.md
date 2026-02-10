# Pitfalls Research

**Domain:** Cycling Analytics Platform (Power-Based Training)
**Researched:** 2026-02-10
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Floating-Point Precision Errors Breaking Exact Match Validation

**What goes wrong:**
Accumulated rounding errors in power calculations cause numerical drift that prevents exact match against Xert's calculations, even when using identical algorithms. Small precision differences compound through multi-step calculations (NP → IF → TSS), leading to divergence that appears as "calculation bugs."

**Why it happens:**
Most floating-point values can't be precisely represented as finite binary values. Every float operation introduces rounding errors on the order of 1 part in 2^53. For power calculations involving exponentiation (Normalized Power uses 4th power), catastrophic cancellation can occur when subtracting two large numbers, magnifying precision loss.

**How to avoid:**
- Use `NUMERIC` type in PostgreSQL for all power calculations requiring exact match (FTP, NP, IF, TSS)
- Store raw power data as integers (watts × 1000) and only convert to decimal for display
- Document precision requirements: "TSS must match Xert within ±0.01"
- Implement deterministic calculation order: same input → same operations → same output
- Add regression tests comparing calculations against known Xert outputs for edge cases

**Warning signs:**
- TSS values differ by small amounts (0.1-0.5) between your platform and Xert
- Different calculation ordering produces different results
- Errors accumulate with longer rides (more data points)
- Results vary between development and production environments

**Phase to address:**
Phase 1: Data Foundation — establish calculation precision strategy before any power algorithm implementation

**Recovery cost:** HIGH — requires recalculating historical data, potential schema migration, and re-validation of all power metrics

---

### Pitfall 2: FIT File Device Variability Breaking Parser

**What goes wrong:**
FIT files from different Garmin devices/firmware versions contain manufacturer-specific extensions and variable field definitions that cause parser failures, data loss, or incorrect power readings. Older devices may omit critical fields (left/right balance, cadence), while newer devices add fields your parser doesn't recognize.

**Why it happens:**
FIT is a binary format with dynamic field definitions that vary between devices. The official FIT SDK specification covers common fields, but Garmin includes device-specific extensions. Field dependencies exist where some fields require previous message types to be interpreted correctly. Compressed timestamp records require careful decompression logic.

**How to avoid:**
- Use battle-tested FIT parsing library (`fit-sdk`, `python-fitparse`) instead of rolling your own
- Implement graceful degradation: continue parsing when unknown fields encountered
- Validate CRC16 checksum but don't fail on corrupt files — log and skip problematic records
- Test against FIT files from multiple device generations: Edge 520, 530, 830, 1030, Fenix 6/7
- Store unparsed FIT file as backup for reprocessing when parser improves
- Validate required fields exist before calculations: timestamp, power, heart rate

**Warning signs:**
- Parser works for your test device but fails for user uploads
- Power data extracted correctly but cadence/HR missing
- Rides from older Garmin devices show zero power despite file containing data
- Parser throws errors on valid FIT files from recent firmware

**Phase to address:**
Phase 1: Data Foundation — validate FIT parser across device matrix before building on top

**Recovery cost:** MEDIUM — reprocess stored FIT files with improved parser, but requires users to re-upload if original files not retained

---

### Pitfall 3: TimescaleDB Chunk Size Misconfiguration Killing Performance

**What goes wrong:**
Default 7-day chunk intervals create thousands of tiny chunks for high-frequency cycling data (1Hz = 3600 rows/hour), causing catastrophic query planning overhead and compression failures. Queries that should take milliseconds timeout after 30+ seconds. Inserts slow to crawl as chunk count explodes.

**Why it happens:**
TimescaleDB's default chunk_time_interval assumes typical time-series data (metrics every 5-60 seconds), not per-second power/HR data. Cycling analytics generates ~3600 rows per hour-long ride. With multiple users and years of history, you quickly hit tens of thousands of sparsely-filled chunks, slowing query planner exponentially.

**How to avoid:**
- Calculate target chunk size: aim for 25% of available RAM per chunk *before* indexing
- For 1Hz cycling data with 16GB RAM: chunk_time_interval should be ~90 days, not 7 days
- Formula: `chunk_rows ≈ (0.25 × RAM_bytes) / row_size_bytes`
- Create separate hypertables for different granularities: `ride_samples` (1Hz), `ride_summary` (per-ride)
- Monitor chunk count: `SELECT count(*) FROM timescaledb_information.chunks` — keep under 1000 active chunks
- Set chunk interval at hypertable creation, changing later requires manual migration

**Warning signs:**
- `EXPLAIN ANALYZE` shows "Planning Time" in seconds instead of milliseconds
- Chunk count grows linearly with ride uploads (1 chunk per ride = bad)
- Compression jobs fail with "too many chunks" errors
- Query performance degrades over time as data accumulates

**Phase to address:**
Phase 1: Data Foundation — set correct chunk_time_interval during initial schema creation

**Recovery cost:** HIGH — requires decompressing data, recreating hypertable with new interval, and re-ingesting all historical data (hours of downtime)

---

### Pitfall 4: Strava API Rate Limit Exhaustion Blocking Multi-User Sync

**What goes wrong:**
Default Strava rate limits (200 requests/15min, 2000/day) are shared across ALL users of your app. With inefficient polling, a handful of active users exhaust the entire app's quota, blocking syncs for everyone. Failed requests still count against limits, causing cascade failures.

**Why it happens:**
Strava rate limits are per-application, not per-user. Naive implementations poll `/athlete/activities` every N minutes for all users, burning 1-2 API calls per check. If fetching activity streams (power/HR data), that's 2+ calls per activity. 100 users × 4 checks/hour × 2 calls = 800 calls/hour → limit hit in 2 hours.

**How to avoid:**
- **Use webhooks** (Strava push model) instead of polling — move from pull to push architecture
- Implement intelligent backoff: exponential delay on 429 errors, respect `X-RateLimit-Reset` header
- Batch user syncs: prioritize users who just completed rides (webhook notification) over background syncs
- Cache activity metadata: only fetch streams for new activities, not every sync
- Track rate limit consumption: log `X-RateLimit-Limit` and `X-RateLimit-Usage` headers
- Request rate limit increase only when approaching capacity with optimized implementation
- Implement user-facing status: "Sync paused due to Strava rate limits, resuming in X minutes"

**Warning signs:**
- 429 errors appearing in logs
- Syncs work for first few users then fail for rest
- Rate limit exhausted early in day (before noon)
- Failed API calls accumulating (each failure counts toward limit)
- Users complaining about "sync stopped working"

**Phase to address:**
Phase 2: API Integration — design rate-limit-aware architecture before multi-user launch

**Recovery cost:** MEDIUM — requires webhook infrastructure (event queue, callback endpoint) and refactoring sync logic, but no data loss

---

### Pitfall 5: Normalized Power Algorithm Edge Cases Creating Validation Failures

**What goes wrong:**
Normalized Power calculations fail or diverge from Xert for edge cases: rides under 10 minutes, rides with dropouts (power = 0 for extended periods), or rides with sudden spikes (sprints). These edge cases are common in real-world data but often missed in testing with synthetic data.

**Why it happens:**
NP algorithm uses 30-second rolling average raised to 4th power. Edge cases break assumptions: short rides have insufficient samples for stable rolling average, power dropouts (stopped at lights) create zeros in rolling average affecting exponential weighting, extreme values (1500W sprints) dominate 4th power calculation. TrainingPeaks docs explicitly warn: "Ignore NP for rides under 10 minutes."

**How to avoid:**
- Implement minimum ride duration check: flag NP as "unreliable" for rides < 10 minutes
- Handle zero power specially: distinguish true zeros (coasting) from missing data (dropout)
- Apply spike detection: smooth outliers before rolling average (95th percentile cap)
- Validate against Xert's edge case handling: test with real-world problematic rides
- Document assumptions: "NP calculation requires continuous power data, min 10 min duration"
- Add quality flags to calculated metrics: `np_reliable: boolean`, `data_quality_score: 0-100`

**Warning signs:**
- NP for short commute rides differs wildly from Xert
- Rides with signal dropouts show inflated or deflated NP
- Sprint-heavy rides have NP >> Xert's calculation
- TSS calculation fails with "NP must be > 0" error

**Phase to address:**
Phase 1: Data Foundation — implement robust NP calculation with edge case handling before TSS/CTL calculations depend on it

**Recovery cost:** MEDIUM — recalculate NP for affected rides, but doesn't require data re-ingestion (only recomputation)

---

### Pitfall 6: PostGIS Coordinate System Confusion Producing Wrong Distances

**What goes wrong:**
Using GEOMETRY type with geographic coordinates (lat/lon) for distance calculations produces nonsensical results: routes appear shorter or longer by orders of magnitude, nearby points separated by 100+ km, or ST_Distance returns degrees instead of meters. Power-based route analysis (elevation gain, grade) becomes garbage data.

**Why it happens:**
GEOMETRY type treats lat/lon as Cartesian coordinates (flat plane), not spherical. Calculating distance using Pythagorean theorem on degrees produces meaningless results. Developers assume PostGIS automatically handles coordinate systems, but it doesn't — you must explicitly choose GEOGRAPHY type or ST_Transform to projected system. **Critical**: PostGIS expects longitude FIRST, latitude SECOND (opposite of common convention).

**How to avoid:**
- **Use GEOGRAPHY type** for GPS coordinates: `geom GEOGRAPHY(POINT, 4326)` — always returns meters
- For routes, store as `GEOGRAPHY(LINESTRING, 4326)` — PostGIS handles great circle calculations
- If using GEOMETRY, always ST_Transform to appropriate UTM zone before distance calculations: `ST_Transform(geom, 26910)` for California
- Document coordinate order: **longitude first, then latitude** — `ST_MakePoint(lon, lat)`
- Add CHECK constraints: `CHECK (ST_X(geom) BETWEEN -180 AND 180)` for longitude validation
- Test with known distances: SF to LA = ~559 km, compare your calculation

**Warning signs:**
- Distance calculations return values in degrees (e.g., 4.47 instead of 559000)
- Routes that should be 50 km show as 5000 km or 0.5 km
- ST_Distance results vary wildly with small coordinate changes
- "Point not in correct SRID" errors appearing
- Imported GPS data shows coordinates swapped (routes in middle of ocean)

**Phase to address:**
Phase 1: Data Foundation — establish correct spatial schema before importing any GPS data

**Recovery cost:** HIGH — requires schema change (GEOMETRY → GEOGRAPHY) and re-importing all route data with coordinate order fix

---

### Pitfall 7: Dynamic FTP Threshold Causing Retroactive Metric Instability

**What goes wrong:**
When FTP changes (user improves fitness), all historical TSS/IF calculations become invalid because they're based on old FTP. Users see their CTL/ATL/TSB "jump" when FTP updates, creating confusing fitness curve discontinuities. Comparing workouts across time becomes meaningless.

**Why it happens:**
TSS formula: `(duration × NP × IF²) / (FTP × 3600) × 100` — FTP is denominator. When FTP increases, all past TSS values mathematically decrease. Most platforms (TrainingPeaks, Xert) handle this by storing "FTP at time of ride" with each activity, but naive implementations use current FTP for all calculations.

**How to avoid:**
- Store `ftp_at_ride_time` with each ride record: snapshot FTP value when ride imported
- Calculate TSS using historical FTP: `TSS = ... / ride.ftp_at_ride_time`
- Track FTP history: `ftp_history` table with `(user_id, date, ftp_value)`
- Implement FTP change detection: when user manually updates FTP, don't retroactively recalculate
- For auto-detected FTP changes: flag rides before/after threshold for user review
- Document behavior: "FTP changes do not affect historical TSS values"

**Warning signs:**
- CTL/ATL charts show sudden jumps unrelated to training changes
- Users complain: "My fitness score dropped after I increased my FTP"
- Historical TSS values change when viewed months later
- Comparing "hard workout last year" to "hard workout this year" shows different TSS despite same effort

**Phase to address:**
Phase 1: Data Foundation — design schema to store historical FTP before calculating any fitness metrics

**Recovery cost:** HIGH — requires backfilling `ftp_at_ride_time` for historical rides (may need to estimate or invalidate old calculations)

---

### Pitfall 8: Row-Level Security Performance Degradation With Data Growth

**What goes wrong:**
Multi-tenant PostgreSQL with RLS policies performs well initially but degrades catastrophically as data grows. Queries that took 10ms at 1000 rides take 10+ seconds at 100,000 rides, even with proper indexes. Sequential scans appear in query plans despite indexed `user_id` column.

**Why it happens:**
RLS policies add implicit WHERE clauses to every query. PostgreSQL planner must verify policy conditions for every row, and complex policies (subqueries, joins) disable query optimization. Without proper indexes on policy columns (`user_id`), planner falls back to sequential scans. As ride count grows per user, even indexed lookups slow due to range scan overhead.

**How to avoid:**
- **Index policy columns first**: `CREATE INDEX ON rides (user_id, timestamp DESC)` — composite index critical
- Keep RLS policies simple: `(user_id = current_setting('app.user_id')::INT)` — no subqueries
- Use `EXPLAIN ANALYZE` with different `app.user_id` values to verify index usage
- Set query planner to prefer index scans: `ALTER TABLE rides SET (fillfactor = 90)`
- Partition tables by user_id range if single-user data exceeds 10GB
- Consider separate schemas per tenant for very large deployments
- Monitor query performance as data grows: test with 10k, 100k, 1M ride sample sizes

**Warning signs:**
- `EXPLAIN ANALYZE` shows `Seq Scan on rides` instead of `Index Scan`
- Query time increases linearly (or worse) with ride count per user
- Database CPU spikes when users load dashboards
- Queries perform differently for different users (some fast, some slow based on data volume)

**Phase to address:**
Phase 2: Multi-User Foundation — design RLS strategy and validate performance before launch

**Recovery cost:** MEDIUM — requires index optimization and potentially query rewriting, but no data migration

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store power data as FLOAT instead of NUMERIC | Faster calculations, smaller storage | Precision drift prevents exact Xert match, debugging is nightmare | Never — use INTEGER (watts × 1000) |
| Poll Strava API instead of webhooks | Simpler implementation, no callback endpoint needed | Rate limits hit immediately with >10 users, poor UX | MVP only, must migrate to webhooks before launch |
| Use default TimescaleDB chunk interval | Zero configuration, works out-of-box | Performance degrades exponentially with data growth | Never — calculate proper interval upfront |
| Parse FIT files directly without library | "Avoid dependency bloat", full control | Breaks with new devices, months of debugging edge cases | Never — use `python-fitparse` or `fit-sdk` |
| Use current FTP for all calculations | Simpler schema, easier queries | Historical data becomes meaningless when FTP changes | Never — store `ftp_at_ride_time` from day 1 |
| Skip CRC validation on FIT files | Faster import, fewer "corrupt file" errors | Silently process corrupted data, producing wrong metrics | Acceptable if storing original FIT for reprocessing |
| Calculate NP without edge case handling | Works for "normal" rides | Fails on short/interrupted rides, validation against Xert fails | MVP only, flag as "beta" feature |
| Use GEOMETRY instead of GEOGRAPHY | Familiar Cartesian math, simpler | Distance calculations completely wrong, unfixable | Never — GEOGRAPHY from start |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Strava API | Polling for new activities every 15 minutes | Use webhook subscriptions, receive push notifications instantly |
| Strava API | Not handling 429 rate limit errors | Implement exponential backoff with `X-RateLimit-Reset` header tracking |
| Strava API | Fetching activity streams on every sync | Cache activity metadata, only fetch streams for new activities |
| Garmin OAuth | Storing access tokens without refresh mechanism | Access tokens expire after 3 months — store refresh token and implement auto-refresh |
| Garmin OAuth | Not checking token expiration before requests | Check expiration timestamp, refresh proactively before API calls |
| FIT File Upload | Accepting any file extension | Validate actual FIT file format (magic bytes), reject non-FIT files early |
| FIT File Upload | Processing synchronously during HTTP request | Process in background job queue, return 202 Accepted immediately |
| FIT File Upload | Deleting FIT file after successful parse | Keep original FIT file for reprocessing when parser improves |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all ride samples into memory | Works fine for single ride, crashes with multi-ride analysis | Stream data with cursor, process in chunks | >10 concurrent users, ~1-2 hour rides |
| N+1 queries for ride list (fetch rides, then samples for each) | Dashboard loads slowly, database connection pool exhausted | Use JOIN or batch fetch with `WHERE ride_id = ANY(...)` | >50 rides per user |
| Full table scan on ride_samples for power curve calculation | Query takes 500ms for 1 user, 50+ seconds for 10 users | Create covering index: `(user_id, timestamp) INCLUDE (power_watts)` | >10,000 total rides |
| Recalculating CTL/ATL on every dashboard load | Dashboard responsive initially, slows to 10+ second loads | Materialize CTL/ATL in `daily_fitness` table, update incrementally | >90 days of training history |
| Storing GPS points as individual rows | Flexible querying, works for prototype | Bloats database (1 point/second = 3600 rows/hour), use LINESTRING | >100 rides with GPS |
| Computing power curves on-demand | Real-time results, no pre-computation | Times out as ride count grows, blocks web workers | >50 rides per user |
| Uncompressed hypertable chunks | Fast inserts, simple setup | Storage explodes (10GB/user/year), backup/restore becomes prohibitive | >100 rides per user |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing user FIT files via public URLs | Anyone with URL can download ride data (GPS tracks, power, HR) | Use signed URLs with 1-hour expiration, require authentication |
| Not validating Strava webhook signatures | Attacker can inject fake ride data | Verify `X-Hub-Signature` header against shared secret |
| Storing OAuth tokens in plaintext | Database breach exposes Strava/Garmin account access | Encrypt tokens at rest (AES-256), decrypt only when needed |
| Allowing users to view other users' detailed ride data | Privacy violation, GPS tracks reveal home addresses | Implement RLS or application-level checks: `WHERE user_id = current_user` |
| Not rate-limiting FIT file uploads | Attacker uploads 1000s of files, fills disk or burns processing quota | Limit to 10 uploads/hour per user, validate file size < 10MB |
| Including power meter serial numbers in public API | Identifies expensive equipment, potential theft targeting | Redact device IDs from public responses, only show to owner |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing TSS for rides < 10 minutes | Misleading "training stress" for short commutes | Display warning: "TSS unreliable for rides under 10 minutes" |
| Not explaining NP vs Average Power | Users confused why numbers differ, distrust platform | Show tooltip: "NP accounts for effort variability, more accurate for intervals" |
| Displaying CTL/ATL without context | Numbers like "45" mean nothing to new users | Add fitness level labels: "0-30: Beginner, 30-60: Intermediate, 60+: Advanced" |
| Syncing rides without progress indication | User uploads 100 rides, stares at blank screen for 5 minutes | Show progress: "Processing ride 47 of 100..." with ETA |
| Recalculating metrics without notification | User's TSS changes overnight, no explanation | Notify: "FTP updated, recalculated last 90 days of metrics" |
| Showing exact match failures as errors | "Your TSS doesn't match Xert" scares users | Frame as feature: "Within 0.5% of Xert calculation" |
| Exposing technical errors to users | "TimescaleDB chunk decompression failed" in UI | Show friendly error: "Temporary issue loading ride data, try again" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **FIT File Parser:** Often missing CRC validation, compressed timestamp handling, manufacturer field support — verify with files from Edge 520, 830, 1030, Fenix 6/7
- [ ] **Normalized Power:** Often missing 30-second rolling average implementation, edge case handling for short rides, zero-power dropout handling — validate against TrainingPeaks test cases
- [ ] **TSS Calculation:** Often missing FTP normalization, intensity factor squaring, duration weighting — must match Xert within 0.5%
- [ ] **CTL/ATL/TSB:** Often missing exponential time weighting (42-day, 7-day constants), initial ramp calculation, day-by-day accumulation — test with known training log
- [ ] **Strava Sync:** Often missing webhook signature validation, rate limit tracking, token refresh logic, activity deletion handling — must handle 429 errors gracefully
- [ ] **GPS Route Display:** Often missing coordinate system transformation, elevation smoothing, grade calculation — verify with known climbs (Mt. Ventoux, Alpe d'Huez)
- [ ] **Power Curve:** Often missing 1-second through 20-minute MMP calculation, ties handling, historical comparison — must match WKO5/GoldenCheetah
- [ ] **Multi-User Isolation:** Often missing RLS policies, user_id indexes, data export restrictions — test with concurrent users accessing different data
- [ ] **Data Export:** Often missing FIT file reconstruction, Strava upload support, TCX/GPX format conversion — users expect to download their data

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Floating-point precision errors | HIGH | 1. Stop new calculations, 2. Migrate to NUMERIC type, 3. Backfill historical calculations, 4. Add regression tests, 5. Communicate to users (4-8 hours downtime) |
| FIT parser breaks with new devices | MEDIUM | 1. Update parser library, 2. Reprocess failed uploads from S3/backup, 3. Notify affected users (1-2 hours, no downtime) |
| Wrong chunk_time_interval | HIGH | 1. Create new hypertable with correct interval, 2. Decompress old chunks, 3. Migrate data (pg_dump/restore), 4. Update app config (4-12 hours downtime) |
| Strava rate limit exhaustion | LOW | 1. Implement exponential backoff, 2. Pause low-priority syncs, 3. Request limit increase (recovers in 15 minutes) |
| NP calculation incorrect | MEDIUM | 1. Fix algorithm, 2. Recalculate NP for all rides, 3. Cascade to TSS/CTL/ATL (1-2 hours, no downtime with batch job) |
| GEOMETRY used instead of GEOGRAPHY | HIGH | 1. Add new GEOGRAPHY column, 2. Convert coordinates with ST_Transform, 3. Update queries, 4. Drop old column (2-4 hours downtime) |
| No historical FTP tracking | HIGH | 1. Add ftp_at_ride_time column, 2. Estimate historical FTP (user interviews, manual logs), 3. Recalculate TSS (partial recovery only) |
| RLS performance degradation | MEDIUM | 1. Add composite indexes on (user_id, timestamp), 2. Simplify policies, 3. Consider partitioning (1-2 hours, no downtime) |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Floating-point precision errors | Phase 1: Data Foundation | Regression tests: TSS matches Xert within 0.01 for 20 test rides |
| FIT parser device variability | Phase 1: Data Foundation | Parse sample files from 6 device models without errors |
| TimescaleDB chunk misconfiguration | Phase 1: Data Foundation | Query plan shows <100ms planning time with 10,000 rides |
| Strava rate limit exhaustion | Phase 2: API Integration | Webhook-based sync, rate limit tracking dashboard, handles 429 gracefully |
| Normalized Power edge cases | Phase 1: Data Foundation | NP calculation matches Xert for short/interrupted/spike rides (10 edge cases) |
| PostGIS coordinate confusion | Phase 1: Data Foundation | Distance SF→LA = 559 ± 1 km, GPS tracks render correctly on map |
| Dynamic FTP instability | Phase 1: Data Foundation | FTP change doesn't alter historical TSS, CTL curve continuous |
| RLS performance degradation | Phase 2: Multi-User Foundation | Query performance <100ms per user with 1000 rides each (10 users) |

---

## Sources

**FIT File Parsing:**
- [Training Stress Scores (TSS) Explained – TrainingPeaks](https://help.trainingpeaks.com/hc/en-us/articles/204071944-Training-Stress-Scores-TSS-Explained)
- [Normalized Power – TrainingPeaks](https://help.trainingpeaks.com/hc/en-us/articles/204071804-Normalized-Power)
- [Formulas from 'Training and Racing with a Power Meter' | Critical Powers](https://medium.com/critical-powers/formulas-from-training-and-racing-with-a-power-meter-2a295c661b46)

**Numerical Precision:**
- [What Every Computer Scientist Should Know About Floating-Point Arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html)
- [Understanding Floating-Point Precision Issues in Python](https://medium.com/@goldengrisha/understanding-floating-point-precision-issues-in-python-a-practical-guide-5e17b2f14057)
- [Floating-Point Arithmetic Issues and Limitations — Python](https://docs.python.org/3/tutorial/floatingpoint.html)

**Strava API:**
- [Strava Rate Limits Documentation](https://developers.strava.com/docs/rate-limits/)
- [How to avoid rate limit | Strava Community](https://communityhub.strava.com/developers-api-7/how-to-avoid-rate-limit-11118)
- [Strava no longer increasing rate limits - Intervals.icu Forum](https://forum.intervals.icu/t/strava-no-longer-increasing-rate-limits/2026)

**TimescaleDB:**
- [Scaling Time Series Data with TimescaleDB Hypertables](https://www.cloudthat.com/resources/blog/scaling-time-series-data-with-timescaledb-hypertables)
- [Timescale Hypertables Best Practices](https://docs.timescale.com/use-timescale/latest/hypertables/about-hypertables/) (Context7)
- [Improve Hypertable and Query Performance](https://docs.timescale.com/use-timescale/latest/hypertables/improve-query-performance/)

**PostGIS:**
- [PostGIS and the Geography Type | Crunchy Data](https://www.crunchydata.com/blog/postgis-and-the-geography-type)
- [PostGIS Geography vs Geometry](http://postgis.net/workshops/postgis-intro/geography.html)
- [PostGIS ST_Transform Documentation](https://postgis.net/docs/ST_Transform.html) (Context7)

**PostgreSQL RLS:**
- [Multi-tenant data isolation with PostgreSQL Row Level Security | AWS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/)
- [Row Level Security for Tenants in Postgres | Crunchy Data](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres)
- [Supabase Row Level Security Complete Guide (2026)](https://designrevision.com/blog/supabase-row-level-security)

**Garmin OAuth:**
- [Garmin Connect OAuth2.0 PKCE Specification](https://developerportal.garmin.com/sites/default/files/OAuth2PKCE_1.pdf)
- [python-garminconnect GitHub](https://github.com/cyberjunky/python-garminconnect)

**Docker & TimescaleDB:**
- [TimescaleDB Docker GitHub](https://github.com/timescale/timescaledb-docker)
- [Quick Guide to Running TimescaleDB on Docker](https://compositecode.blog/2025/03/28/setup-timescaledb-with-docker-compose-a-step-by-step-guide/)
- [How to Install TimescaleDB (2026)](https://oneuptime.com/blog/post/2026-02-02-timescaledb-install/view)

**Power Training:**
- [Cycling Power Zones Explained - TrainingPeaks](https://www.trainingpeaks.com/blog/power-training-levels/)
- [How to Analyze Power Meter Data](https://measuregadget.com/how-to-analyze-power-meter-data/)
- [5 Common Mistakes With Training Data - CTS](https://trainright.com/5-common-mistakes-youre-likely-making-with-your-training-data/)

---
*Pitfalls research for: Cycling Analytics Platform*
*Researched: 2026-02-10*
