# Xert API Documentation (Reverse-Engineered)

> Crawled 2026-04-07 from xertonline.com while authenticated as biker2000on.
> Xert is built with **Svelte** (3.9MB bundle) + **jQuery/AmCharts** (1.4MB activity.js), server-rendered via Laravel/Blade.

---

## Architecture Overview

### Client-Side vs Server-Side

| Component | Location | Notes |
|-----------|----------|-------|
| MPA (Maximal Power Available) | **Client-side** | Computed in `activity.js` using fitness signature + power stream |
| XSS (Xert Strain Score) | **Client-side** | Computed from MPA analysis per activity |
| Fitness Signature progression | **Server-side** | Calculated during activity processing/recalc |
| Adaptive Training Advisor | **Server-side** | `GET /calendar/adaptive-training-advisor` |
| Training Forecast | **Server-side** | `GET /calendar/training-forecast` |
| Training Status (calendar) | **Server-side** | `GET /calendar/training_status/{start}/{end}` |
| Power Curve | **Server-side** | Embedded in advisor response as `current_minute_powers` |

### Authentication

- Session-based (Laravel session cookies)
- CSRF token via hidden `<input name="_token">` + XSRF cookie
- Requests need `X-Requested-With: XMLHttpRequest` header for JSON responses
- Uses Pusher (WebSocket) for real-time notifications

### Tech Stack

- **Backend**: Laravel (PHP) — evidenced by Blade templates, CSRF tokens, route patterns
- **Frontend**: Svelte components (1882 elements on dashboard), jQuery for older pages (activity detail)
- **Charts**: AmCharts/AmStockCharts 3.20.19
- **Calendar**: FullCalendar 3.3.1
- **Maps**: Google Maps (gmaps.min.js)
- **Real-time**: Pusher 7.4.0

---

## Core Data Model

### Fitness Signature

The 4-parameter model that defines a rider's power capabilities:

```json
{
  "pp": 1200,          // Peak Power (watts) — max instantaneous power
  "ftp": 273,          // Threshold Power (watts) — sustainable aerobic power
  "atc": 27770.88,     // High Intensity Energy (joules) — W' equivalent (27.8 kJ)
  "ltp": 204,          // Lower Threshold Power (watts) — aerobic threshold
  "carb_bias": 1.5     // Carbohydrate utilization bias factor
}
```

### XPMC Time Constants (from Settings)

```
Training Load Time Constants:
  Peak:  22 days
  High:  22 days
  Low:   60 days

Recovery Load Time Constants:
  Peak:  12 days
  High:  12 days
  Low:    5 days

Training Responsiveness:
  Low:   0.8   Watts/TL
  High:  0.375 J/TL
  Peak:  73    Watts/TL
```

### XSS Strain Types

- **XLSS** — Low Strain Score (below LTP)
- **XHSS** — High Strain Score (between LTP and TP)
- **XPSS** — Peak Strain Score (above TP, tapping HIE)
- **XSS** — Total Strain Score (XLSS + XHSS + XPSS)

---

## API Endpoints

### Activity Data

#### `GET /activities/{id}/data`
Returns second-by-second activity stream data + fitness signature at time of activity.

**Headers**: `X-Requested-With: XMLHttpRequest`

**Response** (~200KB for a 34min ride):
```json
{
  "power": [221, 193, 196, ...],     // Array[N] — watts per second
  "time": [1775254283000, ...],       // Array[N] — Unix timestamps (ms)
  "hr": [133, 133, 133, ...],        // Array[N] — heart rate (bpm)
  "cad": [78, 79, 82, ...],          // Array[N] — cadence (rpm)
  "spd": [18.44, 18.78, ...],        // Array[N] — speed
  "tgt": [null, null, ...],          // Array[N] — target power (structured workouts)
  "dist": [null, 0.005, ...],        // Array[N] — cumulative distance
  "lat": [35.837, ...],              // Array[N] — GPS latitude
  "lng": [-81.602, ...],             // Array[N] — GPS longitude
  "alt": [346.4, 345.4, ...],        // Array[N] — altitude (meters)
  "t0": 1775254283000,               // Start timestamp (ms)
  "sig": {                           // Fitness signature at activity time
    "pp": 1192,
    "ftp": 272.96,
    "atc": 27770.89,
    "ltp": 203.53,
    "carb_bias": 1.5
  }
}
```

#### `POST /activities/{id}/focus-specificity`
Returns focus type and specificity rating for the activity.

#### `GET /activities/{id}/map?forUser={username}`
Returns map/GPS data for the activity.

#### `GET /activities/download/{id}`
Downloads activity file (FIT/TCX format).

#### `POST /activities/can-download/{id}`
Checks if activity file is available for download.

#### `GET /activities/` (Table View page)
Server-rendered page at `/activities/advanced` with DataTables.
**CSV Export** button available — exports all visible columns.

**Available columns for CSV export:**
- Date, Name, Data Source
- Peak Power, High Intensity Energy, Threshold Power
- Flag, Lock, Elevation, Breakthrough
- Specificity, Focus, Rating, Max Difficulty
- Description, Weight, Maximal Effort Time
- Rouleur (focus duration), Low XSS, High XSS, Peak XSS
- Intensity Ratio, Average Power, Max Power
- Average Speed, Maximum Heart Rate, Average Heart Rate
- XEP (Xert Equivalent Power), XSS (total), KGE
- Durability Score

#### `POST /activities/merge`
Merge duplicate activities.

#### `POST /activities/switch-duplicate`
Switch which of two duplicates is the primary.

#### `POST /activities/unlink-duplicate`
Unlink duplicate activities.

#### `POST /activities/update_matching`
Update matching criteria for activities.

#### `POST /activities/upload/delay`
Upload activity with delay processing.

#### `POST /activities/race-targets`
Set race target parameters for an activity.

#### `DELETE /activities/generate-breakthrough-report/{id}`
Delete/regenerate breakthrough report for an activity.

---

### Adaptive Training Advisor

#### `GET /calendar/adaptive-training-advisor`
**The single richest endpoint** — returns complete training recommendation state.

**Response** (~4.8KB):
```
Top-level fields:
  phase                     — "Continuous" | "Base" | "Build" | etc.
  days_into_training        — int
  ratios                    — {xlss, xhss, xpss} — target XSS distribution ratios
  difficulty                — int (0-100+)
  difficulty_rating         — string e.g. "◆◆◆⬖"
  training_athlete          — athlete type string
  training_focus            — focus duration (seconds)
  training_focus_power      — focus power (watts)
  training_focus_text       — e.g. "348W"
  recommended_athlete       — recommended athlete type
  recommended_focus         — recommended focus duration
  recommended_specificity   — specificity rating
  recommended_spec_rating   — specificity text
  recommended_focus_power   — recommended focus power (watts)
  recommended_focus_text    — e.g. "348W"
  data_quality              — quality rating string
  training_gradient         — {value, text}
  training_grad_val         — {value, text}
  availability              — hours available (int)
  xss_deficit               — current XSS deficit (float, e.g. 209.11)
  xss_goal                  — daily XSS target (float, e.g. 183.1)
  daily_goal_complete       — completion status string
  exercise_type             — "all" | "indoor" | "outdoor" | "virtual"
  exercise_goals            — {indoor, outdoor, virtual, all}
  progress_indicator        — float (-1 to 1, negative = behind)
  progress_indicator_tomorrow — float
  hours_deficit             — float
  activity_deficit          — float
  weekly_hours              — float (e.g. 8.86)
  max_ramp_rate             — float
  weeks_at_max              — int
  mode                      — "Deficit" | "Surplus" | "On Track"
  training_status           — {cat, no, form_cat, color, ts_rating, stars, icon_color, form_ratio, tl_total, rl_total}
  targetXSS                 — {xlss, xhss, xpss} — today's targets
  originalTargetXSS         — {xlss, xhss, xpss} — unadjusted targets
  completedXSS              — completed XSS today
  remainingXSS              — remaining XSS today
  signature                 — {pp, ftp, atc, ltp} — current fitness signature
  current_TP                — current threshold power (int, e.g. 273)
  current_FM                — current focus mastery power (int, e.g. 348)
  at_state                  — adaptive training state object
  form_cat                  — form category
  freshness_is_overridden   — boolean
  tomorrow_status           — tomorrow's predicted status
  target_event_date         — target event date (if set)
  target_event_timestamp    — target event timestamp
  target_athlete_details    — target athlete profile details
  target_athlete            — target athlete type
  ir                        — improvement rate (int, e.g. 3 = Moderate-2)
  based_on_day              — date basis for calculations
  training_advice_as_of     — advice timestamp
  training_advice_as_of_val — advice value
  recovery_needed           — recovery recommendation
  is_availability_restricted — boolean
  current_minute_powers     — {0..37} — 38-point power curve (1min through 38min powers)
  program                   — {type, days_into_training, duration, data, program_starting_values}
  targets_source            — source of target calculations
```

---

### Calendar / Planner

#### `GET /calendar/training_status/{startDate}/{endDate}`
Returns hourly training status slots for the date range.

**Example**: `GET /calendar/training_status/2026-03-31/2026-04-24`

**Response** (~12.7KB): Array of 54 time slot objects:
```json
{
  "date": "string",
  "time": "string",
  "hour": 0,
  "stars": "string",        // training status stars rating
  "no": 0,
  "icon_color": "string",
  "ts_rating": 0,           // numeric training status
  "color": "string"
}
```

#### `GET /calendarSummaryWeekly`
Returns weekly training summary data (~5.5KB). May require query parameters for date range.

#### `GET /calendar/events`
Calendar events for the planner.

#### `GET /calendar/training-forecast`
Training forecast / projected fitness progression. Server-side computation.

#### `GET /calendar/forecast-activities-close/{id}`
Close/complete a forecast activity.

#### `GET /calendar/get-notes`
Retrieve calendar notes.

#### `POST /calendar/save-notes`
Save calendar notes.

#### `POST /calendar/settings`
Update calendar/planner settings.

#### `POST /calendar/swap-forecast-placeholders`
Swap forecast placeholder activities.

#### `GET /calendar/weather/forecast`
Weather forecast for planned activities.

#### `POST /createCalendarEvent`
Create a new calendar event.

#### `POST /deleteCalendarEvent`
Delete a calendar event.

#### `POST /pinCalendarEvent`
Pin/unpin a calendar event.

---

### Fitness Signature & Training Load

#### `GET /getFitnessSignature?path={activityPath}`
Get fitness signature for a specific activity path.

#### `GET /getTrainingLoad?path={activityPath}`
Get training load data for a specific activity path.

#### `GET /recalc`
Trigger full progression recalculation.

---

### Account & Settings

#### `GET /account/user`
Current user account data.

#### `POST /account/settings/freshness-feedback`
Update freshness feedback override settings.

#### `POST /account/settings/training-program`
Update training program settings.

#### `GET /account/check-trickle-status`
Check background sync/trickle processing status.

---

### Workouts & Sessions

#### `POST /autogen-workout`
Auto-generate a workout based on current advisor targets.

#### `GET /workouts/playable-workouts`
List of available playable workouts.

#### `POST /workouts/` (create)
Create a new workout.

#### `POST /workouts/like/{id}`
Like a workout.

#### `POST /workouts/dislike/{id}`
Dislike a workout.

#### `GET /workout-players`
List of connected workout players (EBC, Garmin, Zwift).

#### `GET /workout-player`
Get specific workout player details.

#### `POST /workout/set-workout-player-override`
Override workout player settings.

#### `POST /workout/{id}`
Update a workout.

#### `GET /workout/convert/{id}`
Convert workout format.

#### `POST /workout/to-{format}`
Export workout to specific format.

#### `GET /session-templates-data`
Get workout session templates.

#### `POST /session-template/{id}`
Update a session template.

#### `POST /session-instance/`
Create a new session instance.

#### `POST /session/{id}`
Update a session.

#### `GET /sessions-data`
Get all sessions data.

#### `DELETE /generate-session-report/{id}`
Generate/regenerate session report.

---

### Strava Integration

#### `POST /strava/upload-activity/{id}`
Upload activity to Strava.

#### `POST /strava/get-upload-status/{id}`
Check Strava upload status.

#### `POST /strava/upload-activity-field-defaults/{id}`
Get default field values for Strava upload.

#### `POST /strava/upload-report/{id}`
Get Strava upload report.

---

### Communities & Social

#### `POST /sessions/communities`
Community sessions management.

#### `POST /sessions/communities/leave`
Leave a community session.

#### `POST /sessions/communities/manage`
Manage community session.

#### `GET /sessions/group-communities`
List group communities.

#### `GET /squad-mates-present/{id}` (activity.js)
Check if squad mates are present.

#### `GET /group-chat-url/{id}` (activity.js)
Get group chat URL.

#### `POST /group-chat-self-invite/{id}` (activity.js)
Self-invite to group chat.

#### `POST /activities/create-discussion/{id}` (activity.js)
Create activity discussion thread.

#### `POST /group-chat-unreads/{id}` (activity.js)
Get unread group chat messages.

---

### Admin (if applicable)

#### `POST /admin/update`
System update endpoint.

#### `POST /admin/delete_update`
Delete a system update.

#### `GET /get_updates`
Check for system updates.

---

## MPA Calculation (Client-Side)

MPA is computed in `activity.js` (1.4MB minified). Key observations:

### Algorithm
- Uses the fitness signature (`sig` from `/activities/{id}/data`) as input parameters
- Iterates through second-by-second power data
- Uses `Math.exp` for exponential decay modeling
- Formula fragment found: `mpa = x * (k * x * x + 84 * m * (Y + M))` (minified variable names)
- Chart fields: Power, MPA, TP, Target Power, Cadence, Altitude, Heart Rate, Difficulty, Speed

### Key Math Operations Used
- `Math.sqrt`, `Math.pow`, `Math.min`, `Math.max`
- `Math.atan2`, `Math.abs`, `Math.cos`, `Math.sin`
- `Math.exp` (core of decay model)
- `Math.PI`

### Data Fields in Activity Charts
- `power`, `mpa`, `tp`, `pp` — power metrics
- `strain`, `focus` — derived metrics
- `speed`, `cadence`, `altitude` — sensor data
- `low`, `high`, `Low`, `High` — XSS breakdown
- `watts`, `time` — raw data

---

## Data Export Strategy

### Priority 1: Bulk Activity Data (CSV Export)
1. Navigate to `/activities/advanced` (Table View)
2. Enable ALL columns via "Edit Columns"
3. Set "Show 100 entries" (or paginate)
4. Click **CSV** button to export

This gives per-activity: fitness signature (PP, HIE, TP), XSS breakdown (Low/High/Peak/Total),
focus, specificity, difficulty, breakthrough status, duration, distance, elevation, power metrics, HR, etc.

### Priority 2: Activity Stream Data (Per-Activity API)
For each activity, call `GET /activities/{activityId}/data` with `X-Requested-With: XMLHttpRequest` header.
Returns second-by-second: power, HR, cadence, speed, GPS, altitude + fitness signature at that time.

Activity IDs are alphanumeric slugs (e.g., `b3kbiovg9fzx4vz8`).
Can be scraped from the activities list page HTML.

### Priority 3: Training Advisor State
Call `GET /calendar/adaptive-training-advisor` to get complete current training state:
- Current fitness signature
- Training load / recovery load
- XSS targets and deficits
- Program settings
- 38-point power curve
- Training status and form

### Priority 4: Historical Training Status
Call `GET /calendar/training_status/{startDate}/{endDate}` for historical daily training status ratings.

### Priority 5: Individual Activity Files
Call `GET /activities/download/{activityId}` to download original FIT/TCX files.

---

## Settings to Record Before Subscription Lapses

From `/profile/settings`:

### Fitness Signatures Tab
- Current Fitness Signature: PP, HIE, TP values
- Signature Decay Method (e.g., "Optimal - Default")
- Activities with Locked Signatures (list)

### XPMC Tab
- Time Constants: Training Load (Peak/High/Low days), Recovery Load (Peak/High/Low days)
- Training Responsiveness: Low (Watts/TL), High (J/TL), Peak (Watts/TL)
- Auto-Calc Estimates toggle state

### General Tab
- Weekly Availability schedule (per-day hours + times)
- Heart Rate Derived Metrics toggle
- Time calculation method (Total/Moving/Pedaling)
- Durability Metric method (Total Work/Work Above LTP/Carbs Depleted)
- XSS per Hour Preference
- Max Weekly Hours
- Program Settings (Continuous/Phase, Focus Type, Improvement Rate)

---

## Page-Specific JavaScript Files

| Page | JS File | Size | Purpose |
|------|---------|------|---------|
| All pages | `svelte.js` | 3.9MB | Main Svelte bundle — 59 fetch endpoints, all Svelte components |
| All pages | `core.js` | 17.7KB | Core utilities, trickle status check |
| Dashboard | `my_fitness.js` | 49.4KB | Dashboard-specific Svelte components |
| Activity Detail | `activity.js` | 1.4MB | MPA calculation, chart rendering, AmCharts integration |

---

## Notes

- The app uses **server-side rendering** for initial page loads — most data is embedded in the HTML
- Tab switching on the dashboard (Today/Planner/Activities/Progression/Program) is client-side Svelte — no API calls
- The Planner calendar triggers API calls when navigating months: `training_status` + `calendarSummaryWeekly`
- Activity detail pages trigger: `focus-specificity`, `map`, and `data` endpoints
- The `adaptive-training-advisor` endpoint is the most valuable single API call for replicating Xert's training logic
- MPA computation is the core differentiator and runs entirely in the browser
- 547 activities spanning Jan 2024 - Apr 2026 available
