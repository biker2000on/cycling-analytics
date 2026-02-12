# Phase 2: Coggan Metrics Engine

**Goal**: User sees accurate TSS, NP, CTL/ATL/TSB calculations for every ride
**Requirements**: METR-01, METR-02, METR-03, METR-04, METR-05, METR-06, METR-07
**Dependencies**: Phase 1

## Plan 2.1: Normalized Power (NP) Calculation

**Description**: Implement the Normalized Power algorithm with proper edge case handling for short rides, power dropouts, and extreme spikes.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- NP calculation function, power zone utilities
- `backend/app/schemas/metrics.py` -- NormalizedPowerResult, PowerZoneDistribution
- `backend/tests/test_utils/test_coggan_model.py` -- extensive NP tests with edge cases

**Technical approach**:
- NP algorithm (Coggan standard):
  1. Calculate 30-second rolling average of power
  2. Raise each averaged value to the 4th power
  3. Take the mean of all raised values
  4. Take the 4th root of the mean
- Implementation uses NumPy arrays for performance: `np.convolve` for rolling average, vectorized power/root operations
- Calculations use NumPy float64 for performance; final results rounded to 1 decimal place and stored as PostgreSQL NUMERIC (float64 has ~15-17 significant digits, worst-case error for cycling power data is sub-0.01W, which is negligible)
- Edge cases:
  - Short rides (<30 seconds): return average power (not enough data for rolling average)
  - Power dropouts (value=0): include zeros in rolling average (coasting is valid)
  - Missing power (null): exclude from calculation window, note gap
  - Extreme spikes (>2500W): include but flag for review (legitimate sprints exist)
  - Rides with <50% power data coverage: calculate but flag as low confidence
- Return structured result with confidence flag and warnings

**Acceptance criteria**:
- NP for a steady 200W ride = ~200W (within 1W)
- NP for variable power ride > average power (as expected)
- Short ride (<30s) returns average power with warning
- Ride with dropouts handles zeros correctly
- All calculations use NUMERIC precision (verify no float intermediate storage)
- Test against known NP values from TrainingPeaks/intervals.icu reference

**Estimated complexity**: M

---

## Plan 2.2: TSS, IF, and Power Zones

**Description**: Implement Training Stress Score (TSS), Intensity Factor (IF), and 7-zone Coggan power zone classification.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- extend with TSS, IF calculation, power zone functions
- `backend/app/models/user_settings.py` -- UserSettings model (user_id, ftp_watts NUMERIC, ftp_method enum, ftp_updated_at, hr_zones JSONB nullable, weight_kg NUMERIC nullable)
- `backend/app/routers/settings.py` -- minimal FTP endpoints: POST /settings/ftp (set FTP value), GET /settings/ftp (get current FTP). This unblocks Phase 2 verification; full settings management is in Plan 4.5.
- `backend/app/schemas/settings.py` -- FtpSetting (ftp_watts: Decimal)
- `backend/alembic/versions/004_user_settings.py` -- migration
- `backend/tests/test_utils/test_tss_if.py`
- `backend/tests/test_routers/test_settings_ftp.py`

**Technical approach**:
- Intensity Factor: `IF = NP / FTP`
- TSS: `TSS = (duration_seconds * NP * IF) / (FTP * 3600) * 100`
- Coggan 7-zone model (percentage of FTP):
  - Zone 1 (Active Recovery): <55%
  - Zone 2 (Endurance): 55-75%
  - Zone 3 (Tempo): 76-90%
  - Zone 4 (Lactate Threshold): 91-105%
  - Zone 5 (VO2max): 106-120%
  - Zone 6 (Anaerobic Capacity): 121-150%
  - Zone 7 (Neuromuscular): >150%
- Zone time distribution: calculate seconds spent in each zone for an activity
- UserSettings stores current FTP (manual entry for now, auto-estimation in Phase 4)
- TSS stored on activity record after computation (cached)
- For manual entries without stream data: estimate TSS from avg_power and duration using IF approximation

**Acceptance criteria**:
- TSS for 1-hour ride at FTP = 100 (by definition)
- TSS for 1-hour ride at 75% FTP ~ 56 (0.75^2 * 100)
- IF correctly reflects ratio to FTP
- Power zone boundaries match standard Coggan zones
- Zone distribution sums to total ride time
- Manual entry TSS estimation reasonable (within 10% of actual for steady rides)
- POST /settings/ftp with `{"ftp_watts": 280}` stores FTP value
- GET /settings/ftp returns current FTP value

**Estimated complexity**: M

---

## Plan 2.3: Metric Computation Pipeline

**Description**: Build the background metric computation pipeline that automatically calculates NP, TSS, IF, and zone distribution when an activity is imported, and recalculates when FTP changes.

**Files to create**:
- `backend/app/workers/tasks/metric_computation.py` -- Celery task: compute_activity_metrics(activity_id), recompute_all_metrics(user_id)
- `backend/app/services/compute_service.py` -- orchestrates metric calculation: fetch streams, compute NP/TSS/IF/zones, store results
- `backend/app/models/activity_metrics.py` -- ActivityMetrics model (activity_id FK, ftp_at_computation NUMERIC, normalized_power NUMERIC, tss NUMERIC, intensity_factor NUMERIC, zone_distribution JSONB, variability_index NUMERIC, efficiency_factor NUMERIC nullable, computed_at TIMESTAMPTZ)
- `backend/alembic/versions/005_activity_metrics.py` -- migration
- `backend/tests/test_services/test_compute_service.py`

**Technical approach**:
- Computation triggered automatically after FIT import completes (chained Celery task)
- compute_activity_metrics(activity_id):
  1. Fetch stream data for activity
  2. Fetch user's current FTP (or FTP at ride time if stored)
  3. Calculate NP, IF, TSS, zone distribution
  4. Calculate variability index (NP / avg_power)
  5. Calculate efficiency factor (NP / avg_HR) if HR data available
  6. Store in activity_metrics table
  7. Update activity summary fields (tss, np_watts, intensity_factor)
- recompute_all_metrics(user_id): triggered when FTP changes
  1. Queue on low_priority queue
  2. Fetch all activities for user
  3. Recompute each (incremental: skip if FTP unchanged for that date)
  4. Track progress in batch record
- Store ftp_at_computation with each metric record for audit trail
- Metrics are replaced on recomputation (no versioning per CONTEXT.md decision)

**Acceptance criteria**:
- Uploading a FIT file automatically triggers metric computation
- Activity metrics table populated after computation
- Activity summary fields (tss, np_watts, IF) updated
- FTP change triggers recomputation of all activities
- Recomputation updates metrics and summary fields
- Metrics for manual entries calculated from summary data
- Computation completes within 5 seconds per activity

**Estimated complexity**: M

---

## Plan 2.4: CTL/ATL/TSB Fitness Tracking

**Description**: Implement Chronic Training Load (CTL, 42-day), Acute Training Load (ATL, 7-day), and Training Stress Balance (TSB) using exponentially weighted moving averages.

**Files to create**:
- `backend/app/utils/coggan_model.py` -- extend with CTL/ATL/TSB calculation functions
- `backend/app/models/fitness_metrics.py` -- DailyFitness model (user_id, date DATE, tss_total NUMERIC, ctl NUMERIC, atl NUMERIC, tsb NUMERIC, activity_count INT, threshold_method VARCHAR default 'manual'). Primary key (user_id, date, threshold_method).
- `backend/app/services/fitness_service.py` -- calculate and store daily fitness metrics, handle rest days (TSS=0)
- `backend/app/routers/metrics.py` -- GET /metrics/fitness?start_date=&end_date= (CTL/ATL/TSB time series)
- `backend/app/schemas/metrics.py` -- extend with FitnessDataPoint, FitnessTimeSeries
- `backend/alembic/versions/006_daily_fitness.py` -- migration
- `backend/tests/test_utils/test_fitness.py`
- `backend/tests/test_services/test_fitness_service.py`

**Technical approach**:
- Exponentially weighted moving average formulas:
  - `CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) * (1 - exp(-1/42))`
  - `ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) * (1 - exp(-1/7))`
  - `TSB_today = CTL_today - ATL_today` (positive = fresh, negative = fatigued)
- Rest days (no activity): TSS_today = 0, still apply decay formula
- Multiple activities per day: sum TSS values
- Implementation:
  1. After activity metrics computed, call fitness_service.update_from_date(user_id, activity_date)
  2. Fetch previous day's CTL/ATL
  3. Compute forward from activity_date to today, filling rest days
  4. Store daily_fitness rows for each day
- Incremental update: only recalculate from the changed date forward (not entire history)
- Full rebuild: for initial import of 1500+ rides, calculate entire history once (background task)
- API returns time series: list of {date, ctl, atl, tsb} points for chart rendering

**Acceptance criteria**:
- After importing rides: GET /metrics/fitness returns CTL/ATL/TSB time series
- Rest days show CTL/ATL decay (values decrease toward 0)
- TSB positive after rest, negative after hard block
- New activity upload incrementally updates fitness from that date forward
- Full history rebuild for 1500 rides completes within 30 seconds
- CTL after 42 days of 100 TSS/day ~ 63.2 (1 - 1/e) * 100
- CTL/ATL/TSB values stored as NUMERIC in database

**Estimated complexity**: L

---

## Plan 2.5: Metrics API and Cache Layer

**Description**: Build comprehensive metrics API endpoints with Redis caching for fast dashboard loads. Includes per-activity metrics retrieval and aggregated fitness data.

**Files to create**:
- `backend/app/routers/metrics.py` -- extend with GET /metrics/activities/{id} (single activity metrics), GET /metrics/summary (period summary)
- `backend/app/services/cache_service.py` -- Redis cache wrapper: get/set with TTL, cache key generation, invalidation patterns
- `backend/app/schemas/metrics.py` -- extend with ActivityMetricsResponse, PeriodSummary
- `backend/tests/test_services/test_cache_service.py`
- `backend/tests/test_routers/test_metrics.py`

**Technical approach**:
- Cache strategy (read-through):
  1. Check Redis for cached result (key: `fitness:{user_id}:{threshold_method}:{date_range}`)
  2. Cache miss: query daily_fitness table, serialize, store in Redis with 5-min TTL
  3. Cache invalidation: DEL keys on activity import, FTP change, or metric recomputation
- Per-activity metrics endpoint: returns NP, TSS, IF, zone distribution, VI, EF
- Period summary endpoint: total TSS, ride count, total duration, total distance for a date range
- Redis cache keys:
  - `fitness:{user_id}:manual` -- fitness time series (default threshold method for now)
  - `metrics:{activity_id}` -- per-activity metrics
  - `summary:{user_id}:{start}:{end}` -- period summaries
- Cache invalidation triggered by:
  - Activity import: invalidate fitness and summary caches for user
  - FTP change: invalidate all user caches
  - Activity delete: invalidate all user caches

**Acceptance criteria**:
- GET /metrics/fitness returns data within 100ms (cache hit)
- First request < 2 seconds (cache miss, DB query)
- Subsequent requests < 50ms (Redis cache)
- Cache invalidated on new activity import (fresh data within 5 min)
- Per-activity metrics endpoint returns all computed values
- Period summary returns correct aggregates

**Estimated complexity**: M

---

## Phase 2 Verification

```bash
# 1. Upload a FIT file and verify metrics calculated
curl -X POST http://localhost:8000/activities/upload-fit -F "file=@test_ride.fit"
# Wait for processing...
curl http://localhost:8000/metrics/activities/1
# Expected: {"normalized_power": 215, "tss": 87.3, "intensity_factor": 0.82, "zone_distribution": {...}}

# 2. Check fitness tracking
curl "http://localhost:8000/metrics/fitness?start_date=2025-01-01&end_date=2026-02-10"
# Expected: time series with ctl, atl, tsb values for each day

# 3. Verify power zones
curl http://localhost:8000/metrics/activities/1
# Expected: zone_distribution with seconds per zone, sums to ride duration

# 4. Set FTP and verify recalculation
curl -X POST http://localhost:8000/settings/ftp -d '{"ftp_watts": 280}'
# Wait for recomputation...
curl http://localhost:8000/metrics/activities/1
# Expected: TSS and IF updated based on new FTP

# 5. Run tests
cd backend && uv run pytest tests/test_utils/test_coggan_model.py -v
cd backend && uv run pytest tests/test_services/test_fitness_service.py -v
```
