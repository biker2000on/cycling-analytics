## Phase 4: Threshold Management

**Goal**: User can configure threshold estimation method and switch between views instantly
**Requirements**: THRS-01, THRS-02, THRS-03, THRS-05, THRS-06, THRS-07, THRS-08 (THRS-04 deferred to Phase 10 -- Xert threshold model requires Xert algorithms from Phase 9)
**Dependencies**: Phase 2

### Plan 4.1: Threshold Data Model and History

**Description**: Build the threshold management system that supports multiple estimation methods and stores threshold history over time.

**Files to create**:
- `backend/app/models/threshold.py` -- Threshold model (id, user_id FK, method enum[manual/pct_20min/pct_8min/xert_model], effective_date DATE, ftp_watts NUMERIC, source_activity_id FK nullable, is_active BOOLEAN, notes TEXT nullable, created_at). Unique constraint on (user_id, method, effective_date).
- `backend/app/models/activity_metrics.py` -- extend to include threshold_method and ftp_used_watts on each metric record
- `backend/app/routers/thresholds.py` -- CRUD endpoints: GET /thresholds (history), POST /thresholds (manual set), GET /thresholds/current (active by method), PUT /thresholds/{id}/activate
- `backend/app/schemas/threshold.py` -- ThresholdCreate, ThresholdResponse, ThresholdHistory, ThresholdMethodEnum
- `backend/alembic/versions/008_threshold_management.py` -- migration
- `backend/tests/test_routers/test_thresholds.py`

**Technical approach**:
- Threshold methods enum: manual, pct_20min (95% of 20-min best), pct_8min (90% of 8-min best), xert_model (dynamic, Phase 10)
- Each method maintains its own history: e.g., manual FTP set on 2025-01-01, auto-detected on 2025-01-15
- "Active method" stored in user_settings: which method is currently used for display
- Historical threshold lookup: `get_threshold_at_date(user_id, method, date)` returns the most recent threshold before that date
- ftp_at_ride_time stored per activity metric record for accurate retrospective analysis (THRS-08)
- Setting a new threshold does NOT retroactively change past metrics -- it only affects future computations and explicit recomputation requests

**Acceptance criteria**:
- POST /thresholds with method=manual creates threshold record
- GET /thresholds returns full history sorted by date
- GET /thresholds/current?method=manual returns most recent manual threshold
- Threshold lookup at specific date returns correct historical value
- Multiple methods can coexist (manual + auto-detected)

**Estimated complexity**: M

---

### Plan 4.2: Auto-Detection - 95% of 20-Minute Best

**Description**: Implement automatic threshold estimation using 95% of the best 20-minute power effort from ride history.

**Files to create**:
- `backend/app/services/threshold_service.py` -- threshold estimation logic
- `backend/app/utils/power_analysis.py` -- best_effort(streams, duration_seconds) function, mean_max_power calculations
- `backend/tests/test_utils/test_power_analysis.py`
- `backend/tests/test_services/test_threshold_service.py`

**Technical approach**:
- Best 20-minute power: sliding window over activity stream, find highest 20-minute average power
  - Use NumPy rolling mean: `np.convolve(power, np.ones(1200)/1200, mode='valid')`
  - Handle gaps (nulls) in power data: interpolate or skip windows with >10% missing data
- FTP estimate = best_20min * 0.95
- Search across ALL user activities: find the single best 20-minute effort
- Store as threshold with method=pct_20min, effective_date=date of best effort, source_activity_id=activity that contains the best effort
- Recalculate on new activity import (if new activity contains a better 20-min effort)
- Edge case: user with no rides >20 minutes -- cannot estimate, return null with message

**Acceptance criteria**:
- Given rides with known 20-min best power: estimate matches expected value within 1W
- Estimation updates when a new best 20-min effort is uploaded
- Activities shorter than 20 minutes are excluded
- Result links to source activity (which ride contains the best effort)
- No estimation for users without qualifying rides

**Estimated complexity**: M

---

### Plan 4.3: Auto-Detection - 90% of 8-Minute Best

**Description**: Implement threshold estimation using 90% of the best 8-minute power effort.

**Files to create**:
- `backend/app/utils/power_analysis.py` -- extend with 8-minute best effort
- `backend/app/services/threshold_service.py` -- extend with 8-minute estimation method
- `backend/tests/test_utils/test_power_analysis.py` -- extend

**Technical approach**:
- Same approach as Plan 4.2 but with 8-minute (480 second) window
- FTP estimate = best_8min * 0.90
- More rides qualify (8 min vs 20 min minimum duration)
- Store as threshold with method=pct_8min

**Acceptance criteria**:
- Given rides with known 8-min best power: estimate matches expected value
- Works for rides between 8-20 minutes where 20-min method would not
- Result links to source activity

**Estimated complexity**: S

---

### Plan 4.4: Multi-Method Metric Caching (THRS-06, THRS-07)

**Description**: Pre-compute and cache metrics for ALL threshold methods so users can switch views instantly without recalculation.

**Files to create**:
- `backend/app/services/compute_service.py` -- extend to compute metrics for all methods
- `backend/app/workers/tasks/metric_computation.py` -- extend with compute_all_methods(activity_id)
- `backend/app/routers/metrics.py` -- extend GET /metrics/fitness with ?threshold_method= query param
- `backend/app/services/fitness_service.py` -- extend to maintain per-method fitness series
- `backend/tests/test_services/test_multi_method.py`

**Technical approach**:
- When activity is imported, compute metrics for ALL available threshold methods:
  - For each method, look up threshold at ride date
  - Compute NP (same for all methods), TSS, IF, zones (different per method)
  - Store separate activity_metrics rows per method
  - Update daily_fitness rows per method
- API accepts `threshold_method` query parameter:
  - GET /metrics/fitness?threshold_method=manual (default)
  - GET /metrics/fitness?threshold_method=pct_20min
  - GET /metrics/activities/{id}?threshold_method=pct_8min
- Switching method in UI -> different API call -> instant results from cache
- Storage cost: ~3x current (one row per method per activity per day) -- acceptable for the use case
- When a new threshold is detected for any method: recompute affected metrics in background

**Acceptance criteria**:
- Activity metrics exist for all available methods after import
- GET /metrics/fitness?threshold_method=manual returns different values than ?threshold_method=pct_20min
- Switching method responds within 100ms (pre-cached)
- New threshold auto-detected -> affected metrics recomputed in background
- Daily fitness series maintained per method

**Estimated complexity**: L

---

### Plan 4.5: Threshold Method Selection and User Preferences

**Description**: Let users select their preferred threshold estimation method in profile settings. Selected method becomes the default for all views.

**Files to create**:
- `backend/app/routers/settings.py` -- GET /settings (user preferences), PUT /settings (update preferences)
- `backend/app/models/user_settings.py` -- extend with preferred_threshold_method, calendar_start_day, weight_kg, date_of_birth
- `backend/app/schemas/settings.py` -- UserSettingsResponse, UserSettingsUpdate
- `backend/tests/test_routers/test_settings.py`

**Technical approach**:
- User settings stored in user_settings table (one row per user)
- preferred_threshold_method defaults to 'manual'
- When user changes preferred method:
  1. Update user_settings.preferred_threshold_method
  2. Invalidate Redis caches for this user
  3. No recomputation needed (already pre-cached per Plan 4.4)
- API endpoints that return metrics use user's preferred method unless explicitly overridden by query param
- Settings page also stores: calendar_start_day (default Monday), weight_kg, units preference

**Acceptance criteria**:
- GET /settings returns current preferences
- PUT /settings updates preferred threshold method
- API endpoints default to user's preferred method
- Explicit ?threshold_method= overrides user preference
- Cache invalidated on preference change

**Estimated complexity**: S

---

### Phase 4 Verification

```bash
# 1. Set manual threshold
curl -X POST http://localhost:8000/thresholds -d '{"method":"manual","ftp_watts":275,"effective_date":"2026-01-01"}'

# 2. View auto-detected thresholds
curl http://localhost:8000/thresholds?method=pct_20min
# Expected: auto-detected FTP from best 20-min effort

# 3. Compare methods
curl "http://localhost:8000/metrics/fitness?threshold_method=manual"
curl "http://localhost:8000/metrics/fitness?threshold_method=pct_20min"
# Expected: different TSS/CTL values based on different FTP

# 4. Switch preferred method
curl -X PUT http://localhost:8000/settings -d '{"preferred_threshold_method":"pct_20min"}'
curl http://localhost:8000/metrics/fitness
# Expected: now defaults to pct_20min values

# 5. Verify instant switching (both should be < 100ms)
time curl "http://localhost:8000/metrics/fitness?threshold_method=manual"
time curl "http://localhost:8000/metrics/fitness?threshold_method=pct_20min"

# 6. Threshold history
curl http://localhost:8000/thresholds
# Expected: full history with multiple methods and dates

# 7. Run tests
cd backend && uv run pytest tests/test_services/test_threshold_service.py -v
cd backend && uv run pytest tests/test_services/test_multi_method.py -v
```

