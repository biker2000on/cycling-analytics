
## Phase 8: Dashboard & Charts

**Goal**: User can visualize fitness progression, critical power, and training calendar
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Dependencies**: Phase 6

### Plan 8.1: Fitness Tracker Chart (DASH-01)

**Description**: Build the Performance Management Chart (PMC) showing CTL/ATL/TSB over time with date range selection and threshold method switching.

**Files to create**:
- `frontend/src/pages/DashboardPage.tsx` -- main dashboard with fitness chart as primary view
- `frontend/src/components/charts/FitnessChart.tsx` -- CTL/ATL/TSB line chart with Recharts
- `frontend/src/components/charts/DateRangePicker.tsx` -- date range selector (preset ranges + custom)
- `frontend/src/components/charts/ThresholdMethodSelector.tsx` -- dropdown to switch threshold method
- `frontend/src/api/metrics.ts` -- extend with getFitnessData(start, end, method) API call
- `frontend/src/stores/metricsStore.ts` -- Zustand store for fitness data, date range, method selection

**Technical approach**:
- Recharts `<LineChart>` with three `<Line>` components:
  - CTL (blue, thicker): Chronic Training Load (fitness)
  - ATL (red): Acute Training Load (fatigue)
  - TSB (green, area fill): Training Stress Balance (form/freshness)
- TSB as `<Area>` with fill: green above 0 (fresh), red below 0 (fatigued)
- `<Brush>` component at bottom for zooming into time range
- Date range presets: Last 30 days, Last 90 days, Last 6 months, Last year, All time, Custom
- Threshold method selector: dropdown showing available methods (manual, 95% 20min, 90% 8min)
- Switching method re-fetches data from API (pre-cached, instant response)
- `<Tooltip>` shows CTL, ATL, TSB values and date on hover
- `<ReferenceLine>` at TSB=0 (transition between fresh and fatigued)
- Responsive: full width, minimum height 400px
- Today marker: vertical line or dot on current date

**Acceptance criteria**:
- Fitness chart displays CTL/ATL/TSB lines correctly
- Date range selection updates chart
- Brush component allows sub-range zoom
- Threshold method dropdown changes displayed values
- TSB area fill: green above zero, red below zero
- Tooltip shows all three values on hover
- Chart loads within 1 second (cached data)
- Chart renders 365+ days of data smoothly

**Estimated complexity**: L

---

### Plan 8.2: Critical Power Curve (DASH-02)

**Description**: Build the critical power curve showing the user's best power efforts across standard durations, with date range filtering and comparison overlays.

**Files to create**:
- `frontend/src/components/charts/PowerCurveChart.tsx` -- power curve line chart
- `frontend/src/pages/PowerCurvePage.tsx` -- dedicated power curve page
- `backend/app/routers/metrics.py` -- extend with GET /metrics/power-curve?start_date=&end_date=
- `backend/app/services/power_curve_service.py` -- compute mean max power for all durations
- `backend/app/schemas/metrics.py` -- extend with PowerCurveData, PowerCurvePoint
- `backend/tests/test_services/test_power_curve.py`

**Technical approach**:
- Backend: compute mean max power (MMP) curve
  - For each standard duration (1s, 2s, 5s, 10s, 30s, 1min, 2min, 5min, 10min, 20min, 30min, 60min):
    - Scan all activities in date range
    - Find best average power for that duration (sliding window)
    - Return {duration_seconds, power_watts, activity_id, date}
  - Also compute intermediate points (every 5s up to 5min, every 30s up to 30min, every 1min up to 60min) for smooth curve
  - Cache results in Redis (power curve rarely changes, invalidate on new activity import)
- Frontend: Recharts `<LineChart>` with logarithmic X-axis
  - X-axis: duration (log scale: 1s to 3600s)
  - Y-axis: power (watts)
  - Click on point: shows which activity, date, and exact power value
  - Date range filter: compare current period vs previous period (two overlaid curves)
  - Optional: overlay multiple date ranges (e.g., "this year" vs "last year")
- Reference lines at key durations (5s sprint, 1min VO2max, 5min MAP, 20min FTP proxy)

**Acceptance criteria**:
- Power curve displays with correct peak power at each duration
- Logarithmic X-axis from 1s to 60min
- Click on data point shows source activity and date
- Date range filtering works (shorter range = potentially lower values)
- Comparison overlay shows two curves with different colors
- Cache invalidated when new activity with new best effort imported
- Power curve for user with 100+ activities computes within 5 seconds

**Estimated complexity**: L

---

### Plan 8.3: Training Calendar (DASH-03, DASH-04)

**Description**: Build a monthly calendar view showing activities by day with weekly summary statistics (total TSS, duration, distance).

**Files to create**:
- `frontend/src/pages/CalendarPage.tsx` -- calendar page
- `frontend/src/components/calendar/MonthView.tsx` -- month grid with day cells
- `frontend/src/components/calendar/DayCell.tsx` -- single day showing activity indicators
- `frontend/src/components/calendar/WeeklySummary.tsx` -- weekly totals row
- `frontend/src/components/calendar/CalendarNavigation.tsx` -- month/year navigation
- `backend/app/routers/metrics.py` -- extend with GET /metrics/calendar?year=&month= (daily activity summary)
- `backend/app/schemas/metrics.py` -- extend with CalendarDay, CalendarWeek, CalendarMonth

**Technical approach**:
- Calendar grid: Monday-first by default (configurable in user settings per DASH-03)
- Each day cell shows:
  - Activity count indicator (dot or small bar)
  - Total TSS for the day (color intensity: darker = more TSS)
  - Click to expand or navigate to that day's activities
- Weekly summary row at end of each week:
  - Total TSS, total duration (HH:MM), total distance (km/mi), ride count
- Color coding: TSS intensity (light green = easy week, dark red = hard week)
- Month navigation: arrows for prev/next month, dropdown for jump to month/year
- Backend endpoint returns pre-aggregated data per day:
  - `{date, activity_count, total_tss, total_duration, total_distance, activities: [{id, name, sport_type, tss}]}`
- Use TimescaleDB `time_bucket('1 day', activity_date)` for efficient aggregation

**Acceptance criteria**:
- Calendar displays correct month with Monday-first layout
- Days with activities show indicators and TSS
- Weekly summary row shows correct totals
- Month navigation works
- Click on day shows activities for that day
- Empty days render correctly
- Configurable start day (Monday vs Sunday) from user settings
- Current day highlighted

**Estimated complexity**: M

---

### Plan 8.4: Totals Page with Charts (DASH-05)

**Description**: Build the totals page showing aggregated training statistics with weekly, monthly, and yearly trend charts.

**Files to create**:
- `frontend/src/pages/TotalsPage.tsx` -- totals page with period selector and charts
- `frontend/src/components/charts/TotalsBarChart.tsx` -- stacked bar chart for TSS/duration/distance over time
- `frontend/src/components/charts/TotalsSummaryCards.tsx` -- summary stat cards (total rides, distance, time, TSS)
- `frontend/src/components/charts/PeriodSelector.tsx` -- weekly/monthly/yearly toggle
- `backend/app/routers/metrics.py` -- extend with GET /metrics/totals?period=weekly&start_date=&end_date=
- `backend/app/services/totals_service.py` -- aggregate totals by period
- `backend/app/schemas/metrics.py` -- extend with TotalsPeriod, TotalsResponse

**Technical approach**:
- Period aggregation: weekly, monthly, yearly
- Backend uses `time_bucket` for efficient aggregation:
  - Weekly: `time_bucket('1 week', activity_date)`
  - Monthly: `time_bucket('1 month', activity_date)`
  - Yearly: `time_bucket('1 year', activity_date)`
- Returns: {period_start, activity_count, total_tss, total_duration_hours, total_distance_km, total_elevation_m}
- Frontend: Recharts `<BarChart>` with grouped bars
  - Bars for: TSS, duration, distance (different Y-axes)
  - Toggle between metrics (show TSS bars, or duration bars, or distance bars)
  - Or stacked: TSS + duration combined view
- Summary cards at top: Year-to-date totals (rides, distance, time, TSS, elevation)
- Comparison: show current year vs previous year (optional overlay)
- Year-over-year table: compare months across years

**Acceptance criteria**:
- Weekly totals bar chart displays correctly
- Monthly totals bar chart displays correctly
- Yearly totals display correctly
- Summary cards show accurate year-to-date totals
- Period selector switches between weekly/monthly/yearly views
- Chart responds to date range changes
- Correct handling of partial weeks/months at boundaries

**Estimated complexity**: M

---

### Plan 8.5: Dashboard Layout and Navigation

**Description**: Finalize the dashboard page layout combining the fitness chart as the main view with quick-access widgets for recent activities, upcoming milestones, and training summary.

**Files to create**:
- `frontend/src/pages/DashboardPage.tsx` -- finalize dashboard layout
- `frontend/src/components/dashboard/RecentActivities.tsx` -- last 5 activities widget
- `frontend/src/components/dashboard/TrainingSummary.tsx` -- this week's stats widget
- `frontend/src/components/dashboard/FitnessSnapshot.tsx` -- current CTL/ATL/TSB values
- `frontend/src/components/Layout.tsx` -- update navigation with all pages

**Technical approach**:
- Dashboard layout:
  - Top: FitnessSnapshot (current CTL, ATL, TSB values with trend arrows)
  - Middle: FitnessChart (main PMC chart, takes most space)
  - Bottom-left: RecentActivities (last 5 rides, clickable)
  - Bottom-right: TrainingSummary (this week: rides, TSS, hours, distance)
- Navigation sidebar (update):
  - Dashboard (home icon)
  - Activities (list icon)
  - Calendar (calendar icon)
  - Power Curve (chart icon)
  - Totals (bar chart icon)
  - Settings (gear icon)
- Responsive layout: widgets stack vertically on mobile
- Dashboard data loaded with single API call or parallel requests on mount

**Acceptance criteria**:
- Dashboard shows fitness snapshot with current values
- Fitness chart renders as primary view
- Recent activities widget shows last 5 rides
- Training summary shows this week's totals
- Navigation provides access to all pages
- Responsive: works on desktop and tablet
- Page loads within 2 seconds total

**Estimated complexity**: M

---

### Phase 8 Verification

```bash
# 1. Fitness chart
# Navigate to Dashboard
# Expected: CTL/ATL/TSB chart with correct data, date range picker, method selector

# 2. Critical power curve
# Navigate to Power Curve page
# Expected: curve from 1s to 60min, click on point shows source activity

# 3. Training calendar
# Navigate to Calendar
# Expected: monthly view with activity indicators, weekly summaries, correct TSS totals

# 4. Totals page
# Navigate to Totals
# Expected: bar charts for weekly/monthly/yearly, summary cards with YTD totals

# 5. Dashboard widgets
# Visit Dashboard
# Expected: fitness snapshot, recent activities, weekly summary all populated

# 6. Method switching
# Change threshold method on fitness chart
# Expected: values update instantly (pre-cached data)

# 7. Full build and deploy
docker compose up --build
# Visit http://localhost -> login -> dashboard -> all features working

# 8. Performance check
# Fitness chart with 1 year of data: loads within 1 second
# Power curve with 500+ activities: computes within 5 seconds
# Calendar month view: loads within 500ms
```

