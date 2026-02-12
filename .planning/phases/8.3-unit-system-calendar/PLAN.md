# Phase 8.3: Unit System & Calendar Improvements

**Goal**: Users can switch between metric and US (imperial) units globally, and navigate the calendar with infinite scroll.

**Requirements**: Unit conversion (#3), Calendar infinite scroll (#6)

**Dependencies**: Phase 8

## Plans

### Plan 8.3.1: Backend -- Unit System Setting
- Add `unit_system` column to UserSettings (metric/imperial)
- Alembic migration with server_default="metric"
- Validate against {"metric", "imperial"} in schema

### Plan 8.3.2: Frontend -- Unit Conversion System
- UnitContext + UnitProvider with API sync
- useUnits hook with conversion functions and unit labels
- conversions.ts with pure conversion functions
- Update ~8 components to use hook instead of hardcoded "km"/"m"

### Plan 8.3.3: Frontend -- Unit Toggle on Settings Page
- Metric/Imperial toggle in Settings
- Wired to UnitContext, persists to backend

### Plan 8.3.4: Frontend -- Calendar Infinite Scroll
- Replace prev/next with IntersectionObserver-based infinite scroll
- useInfiniteCalendar hook managing month array
- Sticky month headers with correct active month detection
- "Today" button, cap at 24 months in DOM

## Success Criteria
1. Settings has Metric/Imperial toggle
2. Switching to Imperial shows miles, feet, lbs everywhere
3. Calendar supports infinite scroll
4. "Today" button returns to current month
5. Sticky month header correctly reflects topmost visible month
