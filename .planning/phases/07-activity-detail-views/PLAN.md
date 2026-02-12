## Phase 7: Activity Detail Views

**Goal**: User can analyze activity with power zones, HR data, and route map
**Requirements**: ACTV-03, ACTV-04, ACTV-05, ACTV-06
**Dependencies**: Phase 6

### Plan 7.1: Power Zone Shading on Timeline (ACTV-03)

**Description**: Add 30-second power zone shading to the activity timeline chart. Each 30-second segment is colored by the Coggan power zone based on the user's configured threshold method.

**Files to create**:
- `frontend/src/components/charts/ZoneShadedTimeline.tsx` -- enhanced timeline chart with zone coloring
- `frontend/src/components/charts/ZoneLegend.tsx` -- zone color legend
- `frontend/src/utils/powerZones.ts` -- zone calculation utilities (zone boundaries from FTP, zone colors)
- `backend/app/routers/streams.py` -- extend with GET /activities/{id}/streams/zones (pre-computed zone per 30s block)
- `backend/app/schemas/stream.py` -- extend with ZoneBlock (start_time, end_time, zone, avg_power)

**Technical approach**:
- Backend: compute 30-second zones
  1. Group stream data into 30-second blocks
  2. Calculate average power per block
  3. Determine Coggan zone for each block based on user's active FTP
  4. Return list of ZoneBlock objects
- Frontend: Recharts zone shading
  - Use `<ReferenceArea>` components for each 30-second block, colored by zone
  - Zone colors (standard Coggan): Z1=gray, Z2=blue, Z3=green, Z4=yellow, Z5=orange, Z6=red, Z7=purple
  - Power line overlaid on top of zone shading
  - HR line on secondary Y-axis
  - Legend shows zone names, boundaries, and colors
- Zone boundaries change based on active threshold method (FTP value)
- Threshold method selector on chart: dropdown to switch between methods -> re-fetches zone data with ?threshold_method=

**Acceptance criteria**:
- Timeline chart shows colored 30-second blocks behind power line
- Zone colors match standard Coggan zone colors
- Zone boundaries correct relative to user's FTP
- Switching threshold method changes zone shading (different zones if FTP differs)
- Zone legend displays correctly
- Steady ride at threshold shows mostly yellow (Zone 4)
- Recovery ride shows mostly blue/gray (Zone 1-2)

**Estimated complexity**: L

---

### Plan 7.2: Power Analysis Page (ACTV-04)

**Description**: Build the power analysis detail page showing power distribution, peak efforts, variability index, and detailed power statistics.

**Files to create**:
- `frontend/src/pages/ActivityPowerPage.tsx` -- power analysis page (tab within activity detail)
- `frontend/src/components/charts/PowerDistribution.tsx` -- histogram of power values by zone
- `frontend/src/components/charts/PeakEffortsTable.tsx` -- best efforts at standard durations
- `frontend/src/components/charts/PowerScatterPlot.tsx` -- power vs HR scatter
- `backend/app/routers/metrics.py` -- extend with GET /activities/{id}/power-analysis (power stats, peak efforts, distribution)
- `backend/app/schemas/metrics.py` -- extend with PowerAnalysis, PeakEffort, PowerDistribution
- `backend/app/services/power_analysis_service.py` -- compute power distribution, peak efforts, advanced stats

**Technical approach**:
- Power distribution: histogram of seconds spent at each power level (10W bins), colored by zone
- Peak efforts table: best average power for standard durations (5s, 30s, 1min, 5min, 10min, 20min, 30min, 60min)
  - Backend computes using sliding window on stream data (same as threshold auto-detection)
- Advanced stats displayed:
  - Normalized Power, Average Power, Max Power
  - Variability Index (NP / Avg Power) -- measures how variable the ride was
  - Intensity Factor (NP / FTP)
  - TSS
  - Work (kJ) = average power * duration / 1000
  - Power-to-weight (W/kg) if weight is set
- Power vs HR scatter plot: shows aerobic decoupling (EF drift over time)
- All charts use Recharts (`<BarChart>` for distribution, `<ScatterChart>` for scatter)

**Acceptance criteria**:
- Power distribution histogram shows time in each 10W bin, colored by zone
- Peak efforts table displays correct values for all standard durations
- Advanced stats calculated correctly (TSS, VI, IF, work)
- Power vs HR scatter plot renders
- Page loads within 2 seconds
- Short ride (<5 minutes): some peak effort durations show N/A

**Estimated complexity**: L

---

### Plan 7.3: Heart Rate Analysis Page (ACTV-05)

**Description**: Build the heart rate analysis detail page with HR zones, HR distribution, and HR time-in-zone statistics.

**Files to create**:
- `frontend/src/pages/ActivityHRPage.tsx` -- HR analysis page (tab within activity detail)
- `frontend/src/components/charts/HRDistribution.tsx` -- HR histogram by zone
- `frontend/src/components/charts/HRTimeInZone.tsx` -- horizontal bar chart of time in each HR zone
- `frontend/src/utils/hrZones.ts` -- HR zone calculation (5-zone model based on max HR or LTHR)
- `backend/app/routers/metrics.py` -- extend with GET /activities/{id}/hr-analysis
- `backend/app/schemas/metrics.py` -- extend with HRAnalysis, HRZoneDistribution

**Technical approach**:
- HR zones (5-zone model based on max HR or lactate threshold HR):
  - Zone 1 (Recovery): <68% max HR
  - Zone 2 (Aerobic): 68-82% max HR
  - Zone 3 (Tempo): 83-87% max HR
  - Zone 4 (Threshold): 88-92% max HR
  - Zone 5 (VO2max/Anaerobic): >92% max HR
- User can set max HR or LTHR in settings; zones calculated from whichever is set
- HR distribution: histogram of seconds at each HR value (5 bpm bins)
- Time in zone: horizontal bar chart showing percentage of time in each zone
- HR stats: average HR, max HR, min HR, average HR for each zone
- HR drift: compare first half HR to second half HR at similar power (aerobic decoupling indicator)
- Handle rides without HR data: show message "No heart rate data available"

**Acceptance criteria**:
- HR distribution histogram displays correctly
- Time in zone bars match expected proportions
- HR zones configurable via user settings (max HR or LTHR)
- HR drift indicator calculated
- Rides without HR data show appropriate message
- Zone colors distinct from power zone colors

**Estimated complexity**: M

---

### Plan 7.4: Route Map (ACTV-06)

**Description**: Display the activity route on an interactive map using react-leaflet with OpenStreetMap tiles.

**Files to create**:
- `frontend/src/components/maps/RouteMap.tsx` -- Leaflet map with route polyline
- `frontend/src/components/maps/MapControls.tsx` -- zoom, layer toggle, full-screen
- `frontend/src/pages/ActivityMapPage.tsx` -- map page (tab within activity detail)
- `frontend/src/api/routes.ts` -- getActivityRoute() API call

**Technical approach**:
- react-leaflet `<MapContainer>` with OpenStreetMap tile layer
- Route displayed as `<Polyline>` from GeoJSON coordinates
- Map auto-fits to route bounds on load (`map.fitBounds(route.getBounds())`)
- Color options for polyline:
  - Solid color (default blue)
  - Color by power zone (gradient along route -- stretch goal)
  - Color by elevation (gradient -- stretch goal)
- Start/end markers: green circle for start, red circle for finish
- Elevation profile: small chart below map showing altitude over distance
- CyclOSM tile layer option for cycling-specific map (shows bike lanes, paths)
- Multiple tile layer options: OpenStreetMap, CyclOSM, satellite
- Handle indoor rides: no map tab visible (or show message "Indoor activity - no GPS data")

**Acceptance criteria**:
- Route map displays for outdoor activities
- Route line follows actual GPS path
- Map auto-zooms to fit route
- Start/end markers visible
- Tile layer switchable (OSM, CyclOSM)
- Indoor activities: map tab hidden or shows appropriate message
- Map is interactive (zoom, pan, click)
- Elevation profile shows below map

**Estimated complexity**: M

---

### Phase 7 Verification

```bash
# 1. Zone-shaded timeline
# Navigate to activity detail -> Overview tab
# Expected: timeline with 30-second colored blocks matching power zones

# 2. Power analysis
# Click Power tab on activity detail
# Expected: power distribution histogram, peak efforts table, advanced stats

# 3. HR analysis
# Click HR tab on activity detail
# Expected: HR distribution, time in zone bars

# 4. Route map
# Click Map tab on outdoor activity
# Expected: interactive map with route polyline, start/end markers

# 5. Indoor activity
# View indoor trainer ride
# Expected: no map tab (or "Indoor activity" message), power/HR tabs work

# 6. Threshold method switching on chart
# Change threshold method dropdown on zone-shaded timeline
# Expected: zone colors update to reflect different FTP value

# 7. Build check
cd frontend && npm run build && npm run lint
# Expected: no errors
```
