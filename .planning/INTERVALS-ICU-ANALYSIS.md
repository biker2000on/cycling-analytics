# Intervals.icu Architecture Analysis (April 2026)

Reverse-engineered by crawling the live site to understand tech stack, API patterns, chart types, page structure, and client vs server processing model. This serves as a reference for building the self-hosted cycling analytics platform.

## Tech Stack

- **Frontend**: Vue 3 SPA with Vuetify component library
- **Charts**: D3.js (imported as ES module, not global) rendering to SVG
- **Maps**: Leaflet.js with tile layers
- **Build**: Vite (code-split bundles like `Home-BuoHzqbE.js`, `ActivityCalendar-9PD450UU.js`)
- **Error tracking**: Sentry (`sentry.javascript.vue/9.47.1`)
- **Analytics**: Self-hosted Umami at `umami.intervals.icu`
- **PWA**: Uses Workbox service worker, has `manifest.webmanifest`
- **Auth**: Cookie-based, athlete ID embedded in API paths (e.g., `i237761`)
- **State**: Minimal localStorage (locale, darkMode). All data server-side.

## API Pattern

- Base: `https://intervals.icu/api/`
- Athlete-scoped: `/api/athlete/{athleteId}/...`
- Activity-scoped: `/api/activity/{activityId}/...`
- Token-based pagination on some endpoints (e.g., `&token=mnqomf3cyaixm4ca438`)

## Client vs Server Processing

### Server-side (all heavy computation)

- Stream data (watts, HR, cadence, altitude, temp, velocity) returned pre-processed
- Power curves, HR curves computed server-side
- Power histograms bucketed server-side
- Intervals/laps detected server-side
- Segments matched server-side
- eFTP estimation done server-side
- Power vs HR analysis done server-side
- HR load model computed server-side

### Client-side (rendering and light aggregation only)

- D3 SVG chart rendering
- Fitness chart (CTL/ATL/TSB) computed client-side from activity load data
- Training distribution (Polarized/Pyramidal) computed client-side from zone data
- Totals/summaries aggregated client-side
- Calendar vs List view toggle is purely client-side (same API data)
- Year-over-year comparisons assembled client-side

## Pages & API Endpoints

### Home (Calendar/List View)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/athlete` | GET | Athlete profile |
| `/api/athlete/{id}/subscription` | GET | Subscription status |
| `/api/athlete/{id}/gear` | GET | Gear list |
| `/api/athlete/{id}/weather-forecast` | GET | Weather forecast |
| `/api/athlete/{id}/wellness?oldest=...&newest=...` | GET | Daily wellness entries |
| `/api/athlete/{id}/events?oldest=...&newest=...` | GET | Planned workouts/events |
| `/api/athlete/{id}/activities?oldest=...&newest=...` | GET | Activity summaries |
| `/api/athlete/{id}/activities-sync` | POST | Trigger sync from Strava/Garmin |
| `/api/settings/desktop` | PUT | Save view settings |

- Calendar shows ~8 weeks; List shows same data in a sortable table
- List table columns: Type, Date, Distance, MovingTime, Name, AvgHR, NormPower, Intensity, Load, FTP, Weight, W', AvgPower, AvgSpeed, AvgTemp, Climbing, CrankLength, Work

### Activity Detail - Timeline Tab (default)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/activity/{id}` | GET | Full activity metadata (all summary stats) |
| `/api/activity/{id}/streams?types=time,distance` | GET | Streams for map positioning |
| `/api/activity/{id}/streams?types=time,watts,heartrate,cadence,altitude,distance,temp,velocity_smooth` | GET | Full streams for timeline chart |
| `/api/activity/{id}/segments` | GET | Matched segments |
| `/api/activity/{id}/intervals` | GET | Intervals/laps |

**Summary stats shown**: Distance, Moving Time, Coasting, Avg Speed, Climbing, Intensity, Load, RPE, Feel, Class (Polarized/Pyramidal), Avg/Max HR, TRIMP, Norm Power, Avg Power, Variability, Power/HR, Efficiency, L/R Balance, Fitness/Fatigue/Form, FTP, eFTP, Activity eFTP, W'bal Drop, Work, Calories, CHO Used/In

**Timeline chart**: SVG with groups per metric:
- `mc watts` - raw power
- `mc watts_30s` - 30s smoothed power
- `mc heartrate` - heart rate
- `mc cadence` - cadence
- `mc altitude` - elevation profile
- `mc distance` - distance axis
- `mc temp` - temperature

**Intervals table columns**: Start Time, Elapsed Time, Avg Power, Avg Cadence, Avg Torque, Avg HR, Max HR, Avg Gradient, Intensity, Zone

**Interactive interval editing**: Add (A), Split (S), Merge (M), Delete (D) intervals on the chart

### Activity Detail - Power Tab

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/activity/{id}/power-histogram?bucketSize=25` | GET | Power distribution histogram |
| `/api/activity/{id}/power-curves?types=watts` | GET | This activity's power curve |
| `/api/athlete/{id}/power-curves?curves=42d,s0` | GET | Comparison curves (42-day, season) |
| `/api/activity/{id}/power-vs-hr` | GET | Power vs HR scatter data |
| `/api/activity/{id}/streams?types=time,watts,heartrate,temp,cadence,left_right_balance` | GET | Streams with L/R balance |

**Charts and analysis on this tab**:
- Power zone distribution table (Z1 Active Recovery through Z7 Neuromuscular + Sweet Spot, with time and %)
- Power histogram (25w buckets)
- Power curve chart (this ride vs 42-day vs season, multi-line comparison)
- Best efforts table (5s, 60s, 5m, 10m, 20m, 30m with w/kg and linked to best activities)
- Power/HR ratio chart with aerobic decoupling % analysis
- Power vs HR scatter plot (x=power per minute, y=HR)
- Decoupling % / Power % over time chart with HR reserve overlay
- Power Balance (L/R) chart over power range
- CSV export: `/api/activity/{id}/power-curves.csv?types=watts`

### Activity Detail - HR Tab

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/activity/{id}/hr-histogram?bucketSize=5` | GET | HR distribution histogram |
| `/api/activity/{id}/hr-curve` | GET | This activity's HR curve |
| `/api/athlete/{id}/hr-curves?gap=false&types=watts&curves=42d,s0&version=2` | GET | Comparison HR curves |
| `/api/activity/{id}/time-at-hr` | GET | Time spent at each HR |
| `/api/activity/{id}/hr-load-model` | GET | HR-based load model |

### Activity Detail - Route Tab (Premium feature)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/athlete/{id}/activities-around?activity_id={id}&limit=30` | GET | Nearby/similar activities |

- Route matching and tracking feature (requires subscription)

### Activity Detail - Data Tab

- Shows intervals/laps table (same data as bottom of Timeline tab)

### Fitness Page

- Loads **full year** of data: activities, wellness, events (`oldest=2025-05-03` to `newest=2026-05-03`)
- Also calls `/api/athletes/coaches?v=2`
- **Fitness chart**: D3 SVG with groups:
  - `fitness` - CTL (Chronic Training Load) and ATL (Acute Training Load) lines
  - `form` - TSB (Training Stress Balance) area
  - `x-axis axis` - time axis
  - `date` - date indicator
  - `today` - today marker line
  - `marker` / `markerH` - hover markers
- CTL/ATL/TSB computed **client-side** from activity training load values

### Power Page

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/athlete/{id}/power-curves?curves=42d,s0,s1&includeRanks=true` | GET | 42-day, this season, last season with rankings |
| `/api/rankings?sport=Ride` | GET | Community rankings |

- Power curve comparison chart across multiple time periods
- eFTP estimates per period (calculated using FastFitness.Tips curves and Morton's 3-parameter critical power model)
- Power profile (requires DOB and height)
- CSV export: `/api/athlete/{id}/power-curves.csv?curves=42d,s0,s1&type=Ride`

### Pace Page

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/athlete/{id}/pace-curves?curves=42d,s0,s1&pmType=CS` | GET | Same pattern as power but for running |

### Totals Page

- Year-to-date activities, wellness, events (same endpoints as Home, wider date range)
- All computed **client-side**:
  - Total distance, duration, climbing, load, calories, work
  - Per-sport breakdown (e.g., Ride: 73h39m, 1207mi, Load 3632)
  - Zone distribution tables: Combined, Power, HR
  - Training distribution analysis: Polarized, Pyramidal, HIIT, Base
  - Polarization Index (threshold-based metric, e.g., 0.69)

### Compare Page

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/athlete/{id}/get-power-hr-curve` | POST | Called per comparison period (4x for 4 years) |
| `/api/athlete/{id}/wellness?oldest=...&newest=...` | GET | Fetched per year (4 separate requests) |

- Year-over-year comparison charts:
  - Cumulative Distance
  - Cumulative Moving Time
  - Monthly Time
  - Power vs Heart Rate (scatter with trend lines per year)
  - Monthly Distance

## Vue Component Names (from code-split bundles)

Key component files observed in the JS bundle loading:
- `Home` - main calendar/list page
- `ActivityCalendar` - calendar grid view
- `ActivityStoreView` - activity data store
- `ViewToggle` - calendar/list toggle
- `PlotCalendarOptionsDialog` - chart options for calendar
- `EditEventDialog` / `ViewEventDialog` - event CRUD
- `CombinedZoneDetail` - zone distribution display
- `WellnessOptionList` - wellness field configuration
- `RampRateChartD3` - ramp rate chart (D3-based)
- `FormChartD3` - form/TSB chart (D3-based)
- `FitnessPlotsToolbar` - fitness chart controls
- `SportSettingsTab` / `SportDisplayItem` - sport configuration
- `ActivityBulkOpDialog` / `ActivityBulkOps` - bulk operations
- `MergeRoutesDialog` - route merging
- `Fitness` - fitness page logic
- `TrainingLogUtils` - training log helpers
- `PlanUtil` - plan builder utilities
- `FindAthleteDialog` - athlete search
- `AskACoachBox` - coaching feature

## Key Architectural Takeaways for Self-Hosted Clone

1. **Server does the heavy lifting**: Stream processing, interval detection, power curve calculation, eFTP estimation all happen server-side. This is the right approach for a self-hosted app where you control the backend.

2. **Client fetches pre-computed data**: The frontend is primarily a visualization layer. Streams come down as arrays, charts are rendered from those arrays. No complex math in the browser.

3. **Streams are the core data model**: Time-aligned arrays of watts, HR, cadence, altitude, etc. This is the fundamental unit of data. Everything derives from streams.

4. **D3 + SVG for all charts**: No Canvas, no chart library wrapper. Custom D3 bindings render directly to SVG elements. This gives full control over interactivity (hover, click intervals, markers).

5. **Leaflet for maps**: Lightweight, open-source map rendering with tile layers.

6. **Vue 3 + Vuetify**: Component-based UI with Material Design. Each page/feature is a code-split chunk loaded on demand.

7. **RESTful API with athlete/activity scoping**: Clean separation between athlete-level data (power curves, wellness, activities list) and activity-level data (streams, intervals, segments).

8. **Date-range based data loading**: Calendar loads ~8 weeks, fitness loads ~1 year, totals loads YTD. The range determines what gets fetched.

9. **CSV export available**: Power curves and power-vs-HR data are exportable as CSV, suggesting users want to analyze their data externally too.

10. **Interval editing is a first-class feature**: Users can add, split, merge, and delete intervals directly on the timeline chart. This is a key differentiator vs simpler analytics tools.
