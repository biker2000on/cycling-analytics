# Phase 8.4: Dark Mode & UI Modernization

**Goal**: Users can toggle between light and dark themes. UI is modernized with improved visual hierarchy, consistent spacing, and polished components.

**Requirements**: Dark/light mode + UI modernization (#7)

**Dependencies**: Phase 8 (benefits from 8.1-8.3 being complete)

## Plans

### Plan 8.4.1: Backend -- Theme Preference Setting
- Add `theme` column to UserSettings (light/dark/system)
- Alembic migration with server_default="light"
- Validate against {"light", "dark", "system"}

### Plan 8.4.2: Frontend -- Theme System with CSS Custom Properties
- [data-theme="dark"] overrides in variables.css
- ThemeContext + ThemeProvider with API sync
- useTheme hook, "system" mode via matchMedia listener

### Plan 8.4.3: Frontend -- Theme Toggle in UI
- Topbar icon button (sun/moon/monitor) cycling themes
- Settings page "Appearance" section with radio group
- Both controls synced via ThemeContext

### Plan 8.4.4: Frontend -- UI Modernization Pass
- CSS-only improvements: typography, spacing, transitions
- Consistent spacing scale, font tokens
- Card hover states, table alternating rows
- Both light and dark themes polished

## Success Criteria
1. Dark mode toggle in topbar works instantly
2. Settings page offers Light/Dark/System theme options
3. All pages render correctly in dark mode
4. UI feels modern with consistent spacing and smooth transitions
5. Both themes look polished and cohesive
