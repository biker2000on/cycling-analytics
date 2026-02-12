## Phase 6: Frontend Foundation

**Goal**: User can access web interface, view activity list, and drill into basic activity details
**Requirements**: ACTV-01, ACTV-02
**Dependencies**: Phase 5

### Plan 6.1: React + Vite + TypeScript Project Setup

**Description**: Initialize the frontend project with Vite, React 18, TypeScript, and core dependencies. Set up project structure, routing, and API client.

**Files to create**:
- `frontend/package.json` -- project config with all dependencies
- `frontend/vite.config.ts` -- Vite config with proxy to backend API
- `frontend/tsconfig.json` -- TypeScript config
- `frontend/index.html` -- entry HTML
- `frontend/src/main.tsx` -- React entry point
- `frontend/src/App.tsx` -- root component with router
- `frontend/src/api/client.ts` -- Axios instance with JWT interceptor, base URL config
- `frontend/src/api/types.ts` -- TypeScript types matching backend Pydantic schemas
- `frontend/src/stores/authStore.ts` -- Zustand store for auth state (token, user, login/logout)
- `frontend/src/stores/activityStore.ts` -- Zustand store for activity list/detail
- `frontend/src/types/activity.ts` -- Activity, ActivityStream, ActivityMetrics types
- `frontend/src/types/metrics.ts` -- FitnessData, PowerZone types
- `frontend/src/components/Layout.tsx` -- app shell with navigation sidebar
- `frontend/src/components/ProtectedRoute.tsx` -- auth guard component
- `frontend/.eslintrc.cjs` -- ESLint config for React+TS

**Technical approach**:
- Create with `npm create vite@latest frontend -- --template react-ts`
- Dependencies: react, react-dom, react-router-dom, axios, zustand, recharts, react-leaflet, leaflet, date-fns
- Dev deps: @types/leaflet, eslint, prettier, @vitejs/plugin-react
- Vite proxy: `/api` -> `http://localhost:8000` for dev (avoids CORS)
- API client: Axios with interceptor that adds Authorization header from auth store
- Token refresh: interceptor catches 401, attempts refresh, retries original request
- Zustand for state management (lightweight, no boilerplate vs Redux)
- React Router v6 with routes: /login, /setup, /activities, /activities/:id, /dashboard, /settings
- Layout component: sidebar navigation (Dashboard, Activities, Settings), top bar with user info

**Acceptance criteria**:
- `npm run dev` starts Vite dev server with HMR
- App renders at http://localhost:5173
- API calls proxy to backend (no CORS errors)
- Login page displayed for unauthenticated users
- After login: redirected to activity list
- TypeScript compiles without errors
- Navigation between routes works

**Estimated complexity**: M

---

### Plan 6.2: Authentication UI

**Description**: Build login page, registration page, and first-run setup wizard in the frontend.

**Files to create**:
- `frontend/src/pages/LoginPage.tsx` -- email/password form, error handling
- `frontend/src/pages/RegisterPage.tsx` -- registration form
- `frontend/src/pages/SetupWizardPage.tsx` -- first-run setup: create account, optional Garmin/Strava connect, set FTP
- `frontend/src/components/auth/LoginForm.tsx`
- `frontend/src/components/auth/RegisterForm.tsx`
- `frontend/src/api/auth.ts` -- login(), register(), refresh(), logout() API calls

**Technical approach**:
- Login form: email + password, submit calls POST /auth/login, stores token in Zustand + localStorage
- Registration form: email + password + display_name + confirm password
- Setup wizard (shown when /setup/status returns setup_complete=false):
  1. Step 1: Create admin account (email, password, display name)
  2. Step 2: Set initial FTP (optional, can skip)
  3. Step 3: Connect Garmin (optional, save credentials)
  4. Step 4: Connect Strava (optional, OAuth redirect)
- Form validation: email format, password minimum length, password match
- Error display: inline field errors + toast notifications for API errors
- Token persistence: store in localStorage, rehydrate on app load

**Acceptance criteria**:
- Login with valid credentials -> redirected to /activities
- Login with invalid credentials -> error message displayed
- Registration creates account and logs in
- Setup wizard appears on first visit to fresh instance
- Setup wizard steps complete successfully
- Token persists across page refresh

**Estimated complexity**: M

---

### Plan 6.3: Activity List Page

**Description**: Build the activity list page with sortable table, pagination, and basic filters.

**Files to create**:
- `frontend/src/pages/ActivityListPage.tsx` -- main activity list page
- `frontend/src/components/activities/ActivityTable.tsx` -- sortable table component
- `frontend/src/components/activities/ActivityFilters.tsx` -- date range, sport type filters
- `frontend/src/components/activities/UploadButton.tsx` -- FIT file upload trigger
- `frontend/src/components/activities/UploadModal.tsx` -- drag-and-drop upload modal with progress
- `frontend/src/components/common/Pagination.tsx` -- reusable pagination component
- `frontend/src/components/common/SortHeader.tsx` -- sortable column header
- `frontend/src/api/activities.ts` -- getActivities(), uploadFit(), deleteActivity() API calls

**Technical approach**:
- Table columns: Date, Name, Duration, Distance, TSS, NP, IF, Sport Type, Source
- Sortable by: date (default DESC), duration, distance, TSS
- Pagination: 25 activities per page, load more button or page numbers
- Upload: drag-and-drop zone or file picker, supports .fit and .zip files
- Upload progress: show progress bar, then polling for processing status via GET /tasks/{id}
- After upload complete: activity appears in list (auto-refresh or manual refresh)
- Date formatting: relative for recent ("2 hours ago"), absolute for older ("Jan 15, 2026")
- Distance/duration formatting: km/mi based on user preference, HH:MM:SS duration
- Empty state: friendly message for users with no activities yet, prominent upload CTA
- Click on row -> navigate to /activities/:id

**Acceptance criteria**:
- Activity list displays with all columns populated
- Sorting by each column works (click header to toggle ASC/DESC)
- Pagination loads next page of activities
- FIT file upload via drag-and-drop works
- Upload progress indicator shown during processing
- Newly uploaded activity appears in list after processing
- Click on activity navigates to detail page
- Empty state shown for new users

**Estimated complexity**: M

---

### Plan 6.4: Activity Detail Page - Basic View

**Description**: Build the activity detail page showing metadata, summary stats, and a basic power/HR timeline chart.

**Files to create**:
- `frontend/src/pages/ActivityDetailPage.tsx` -- main detail page with tabs
- `frontend/src/components/activities/ActivityHeader.tsx` -- title, date, sport type, metadata
- `frontend/src/components/activities/ActivityStats.tsx` -- summary stats grid (duration, distance, TSS, NP, IF, avg power, max power, avg HR, max HR, elevation)
- `frontend/src/components/charts/TimelineChart.tsx` -- Recharts line chart with power and HR over time
- `frontend/src/api/streams.ts` -- getActivityStreams(), getStreamSummary() API calls
- `frontend/src/api/metrics.ts` -- getActivityMetrics() API call

**Technical approach**:
- Layout: header with metadata -> stats grid -> tabbed content area (Overview, Power, HR, Map)
- Overview tab: timeline chart + stats grid
- Timeline chart using Recharts:
  - Dual Y-axis: left for power (watts), right for heart rate (bpm)
  - `<LineChart>` with `<Line>` for power (blue) and HR (red)
  - `<Brush>` component for zoom/pan on time axis
  - Use summary endpoint (500 points) for initial load, full data on zoom
  - `<Tooltip>` shows values at cursor position
  - `<ReferenceLine>` at FTP level (dashed horizontal line)
- Responsive: full width on desktop, scrollable on mobile
- Loading state: skeleton loader while fetching stream data
- Error state: message if stream data unavailable (manual entry)

**Acceptance criteria**:
- Activity detail page loads with metadata and stats
- Timeline chart shows power and HR over time
- Brush component allows zooming into time range
- Tooltip shows values on hover
- FTP reference line visible on chart
- Manual activity shows stats only (no chart, message "No stream data")
- Page loads within 2 seconds (summary endpoint used)
- Back navigation returns to activity list

**Estimated complexity**: L

---

### Plan 6.5: Frontend Docker Integration

**Description**: Add frontend build to Docker Compose, serve built React app through Nginx alongside API proxy.

**Files to create**:
- `frontend/Dockerfile` -- multi-stage build (npm install -> npm run build -> serve via Nginx)
- `nginx/nginx.conf` -- update to serve frontend static files and proxy /api to backend
- `docker-compose.yml` -- update to include frontend build

**Technical approach**:
- Frontend Dockerfile:
  - Stage 1: Node 20 alpine, npm ci, npm run build (produces dist/)
  - Stage 2: Nginx alpine, copy dist/ to /usr/share/nginx/html
- Nginx config:
  - Location /api -> proxy_pass http://api:8000
  - Location / -> try_files $uri /index.html (SPA fallback)
  - Gzip compression for JS/CSS/HTML
  - Cache headers for static assets (1 year for hashed files)
- docker-compose.yml adds frontend service or combines into Nginx service
- Dev mode: `docker-compose.dev.yml` still runs frontend via `npm run dev` locally

**Acceptance criteria**:
- `docker compose up --build` serves full app (frontend + API)
- http://localhost shows React app
- API calls work through Nginx proxy
- SPA routing works (refresh on /activities/1 loads correctly)
- Static assets served with proper cache headers
- Build size reasonable (<2MB for initial load)

**Estimated complexity**: M

---

### Phase 6 Verification

```bash
# 1. Frontend dev server
cd frontend && npm run dev
# Visit http://localhost:5173 -- should see login page

# 2. Login flow
# Login with test credentials -> redirected to activity list

# 3. Activity list
# Expected: table with activities, sortable columns, pagination

# 4. Upload FIT file
# Drag .fit file onto upload zone -> progress -> activity appears in list

# 5. Activity detail
# Click activity -> detail page with stats and timeline chart
# Zoom chart with brush -> chart updates

# 6. Docker build
docker compose up --build
# Visit http://localhost -> full app works

# 7. Build check
cd frontend && npm run build
# Expected: no TypeScript errors, build succeeds
```

