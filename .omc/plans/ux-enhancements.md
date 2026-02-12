# UX Enhancement Phases

## Context

### Original Request
Add 7 UX feature areas to the cycling-analytics project as new phases after the existing Phase 8 (Dashboard & Charts). These features focus on data import polish, user preferences, and visual modernization.

### Research Findings

**Backend state**: All integration endpoints already exist (Garmin connect/sync/status/disconnect, Strava authorize/callback/sync/backfill/status/disconnect). Task status endpoint exists but progress is hardcoded to coarse buckets (PENDING=0%, STARTED=50%, SUCCESS=100%). Celery tasks (fit_import, garmin_sync, strava_sync) do not call `self.update_state()` for granular progress. Settings model has `UserSettings` with FTP, weight, threshold method, calendar_start_day, DOB -- but no `unit_system` or `theme` fields.

**Frontend state**: React 19 + Vite 7 + TypeScript. CSS custom properties in `variables.css` (light theme only, no dark variant). `format.ts` has hardcoded metric formatters (km, m). `UploadButton.tsx` uses Axios `onUploadProgress` for upload % but shows "processing..." generically after upload completes. `CalendarPage.tsx` uses prev/next buttons with `useState` for year/month -- no infinite scroll. `SettingsPage.tsx` only has FTP input. `Layout.tsx` has sidebar + topbar, no theme toggle. Zustand for state management.

**Components displaying units** (need conversion): `ActivityTable.tsx` (distance "km" header), `ActivityStats.tsx` (distance "km", elevation "m"), `TrainingSummary.tsx` ("km"), `WeeklySummary.tsx`, `TotalsSummaryCards.tsx`, `TotalsBarChart.tsx`, `DayCell.tsx`, `format.ts` formatters.

**Strava OAuth callback gap**: The current `strava_callback` endpoint (`GET /integrations/strava/callback`) returns a JSON `StravaCallbackResponse(connected=True, athlete_id=...)`. When Strava redirects the user's browser to this URL after OAuth authorization, the browser displays raw JSON. This must be fixed to redirect the browser to the frontend.

**Frontend TaskStatus type gap**: The existing `TaskStatus` interface in `frontend/src/api/types.ts` has only `{ task_id, status, result }` -- it is missing `progress`, `stage`, `detail`, and `error` fields that the backend returns. This must be addressed as part of the processing status work.

## Phase Organization

The 7 features are grouped into **4 phases** based on logical coupling and dependency:

| Phase | Name | Features | Rationale |
|-------|------|----------|-----------|
| 8.1 | Upload & Processing UX | Drag-and-drop upload (#2), Upload progress fix (#4), Post-upload processing status (#5) | All three concern the data-import-to-processed pipeline. The upload progress fix requires backend Celery changes that also power the processing status display. Drag-and-drop modifies the same UploadButton component. |
| 8.2 | Integration Settings & Backfill | Garmin & Strava connection UI (#1), Strava OAuth redirect fix | Standalone settings panel work. Backend endpoints already exist; this is pure frontend + minor backend additions. Includes the critical Strava callback redirect fix to make the OAuth flow browser-compatible. |
| 8.3 | Unit System & Calendar | Unit conversion (#3), Calendar infinite scroll (#6) | Both are cross-cutting user preference features. Unit conversion adds a setting + global context + updates to many components. Calendar scroll is a self-contained UI improvement. Grouped because both depend on the settings infrastructure and are medium-complexity. |
| 8.4 | Dark Mode & UI Modernization | Dark/light mode + UI modernization (#7) | Touches every CSS file and component. Must come last because earlier phases may add new components/styles that also need dark mode support. |

**Execution order**: 8.1 -> 8.2 -> 8.3 -> 8.4 (8.2 and 8.3 could be parallelized, but 8.4 must be last)

---

## Phase 8.1: Upload & Processing UX (INSERTED)

**Goal**: Users see real-time progress during file upload AND backend processing, with drag-and-drop support on the Activities page.

**Requirements**: Features #2 (drag-and-drop), #4 (upload progress fix), #5 (post-upload processing status)

**Dependencies**: Phase 8

### Plan 8.1.1: Backend -- Granular Celery Task Progress

**Description**: Add `self.update_state()` calls to all Celery tasks so the existing `/tasks/{task_id}` endpoint returns meaningful progress percentages instead of hardcoded values. Update `task_service.py` to read the custom state metadata.

**Files to modify**:
- `backend/app/workers/tasks/fit_import.py` -- Add `self.update_state(state='PROGRESS', meta={'current': N, 'total': M, 'stage': 'parsing'|'streams'|'laps'|'metrics'})` at each processing stage. Stages: parsing FIT (10%), inserting streams (10-70% scaled by batch), inserting laps (80%), updating activity (90%), complete (100%).
- `backend/app/workers/tasks/garmin_sync.py` -- Add progress updates per activity synced: `current=i, total=len(garmin_activities)`.
- `backend/app/workers/tasks/strava_sync.py` -- Add progress updates per activity in both `sync_strava_activities` and `strava_historical_backfill`.
- `backend/app/services/task_service.py` -- Update `get_task_status()` to read `result.info` when state is `'PROGRESS'` and extract `current`, `total`, `stage`. Calculate real percentage.
- `backend/app/schemas/task.py` -- Add `stage: str | None` and `detail: str | None` fields to `TaskStatusResponse`.

**Technical approach**:
- Celery's `self.update_state(state='PROGRESS', meta={...})` stores custom metadata in the result backend.
- `AsyncResult.info` returns this metadata when state is `'PROGRESS'`.
- For `fit_import`: 5 stages with weighted progress (parse=10%, streams=60%, laps=10%, metadata=10%, done=10%). Stream insertion loops report per-batch progress within the 60% window.
- For sync tasks: `current/total` activities provides natural progress.
- Keep backward compatibility: PENDING/STARTED/SUCCESS/FAILURE still work as before.

**Passing the task instance to helper functions**:

The `_insert_streams()` and `_insert_laps()` functions in `fit_import.py` are standalone module-level functions, NOT methods on the Celery task class. They cannot call `self.update_state()` directly because they have no reference to `self`. The solution is to pass the task instance as an explicit parameter:

1. Change the signatures of both helpers to accept an optional task parameter:
   - `def _insert_streams(session, activity_id, streams, log, task=None):`
   - `def _insert_laps(session, activity_id, laps, log, task=None):`
2. In `process_fit_upload()`, pass `self` when calling these helpers:
   - `stream_count = _insert_streams(session, activity_id, result.streams, log, task=self)`
   - `lap_count = _insert_laps(session, activity_id, result.laps, log, task=self)`
3. Inside `_insert_streams()`, after each batch flush, call:
   ```python
   if task is not None:
       batch_progress = 10 + int(60 * (batch_start + len(batch)) / total)
       task.update_state(state='PROGRESS', meta={
           'current': batch_progress, 'total': 100,
           'stage': f'Inserting stream data {batch_start // STREAM_BATCH_SIZE + 1}/{(total + STREAM_BATCH_SIZE - 1) // STREAM_BATCH_SIZE}'
       })
   ```
4. Inside `_insert_laps()`, call `task.update_state(...)` once before insertion with stage "Analyzing laps".
5. The `task=None` default keeps the functions callable without a task reference (e.g., in tests or non-Celery contexts).

**Acceptance criteria**:
- `GET /tasks/{task_id}` returns `progress` values between 0-100 that advance as the task runs
- `stage` field reflects current processing step (e.g., "Parsing FIT file", "Inserting stream data 3/12", "Computing metrics")
- Existing tests pass without modification
- New tests verify progress reporting for each task type

**Estimated complexity**: M

---

### Plan 8.1.2: Backend -- Multi-file Upload Endpoint

**Description**: Extend the upload endpoint to accept multiple files in a single request, and properly handle .zip files containing multiple FIT files. Return an array of task IDs.

**Files to modify**:
- `backend/app/routers/activities.py` -- Add `POST /activities/upload` endpoint accepting `List[UploadFile]`. For each file: if `.fit`, process directly; if `.zip`, extract and process each `.fit` inside. Return `List[ActivityUploadResponse]`. Keep existing `POST /activities/upload-fit` for backward compatibility.
- `backend/app/services/import_service.py` -- Add `handle_zip_upload()` that extracts zip contents, validates each entry is a FIT file, and calls `handle_upload()` for each. Add `handle_multi_upload()` orchestrating multiple files.

**Technical approach**:
- Use Python's `zipfile.ZipFile` to extract `.zip` contents in memory.
- Validate each extracted file has FIT magic bytes before processing.
- Return partial results: some files may succeed while others fail (duplicates, invalid format).
- Rate limiting applies per-request, not per-file-within-zip.
- Response schema: `{ uploads: [{ filename, activity_id?, task_id?, error? }] }`.

**Zip upload safety limits** (aligned with existing `batch_import_service.py` constants):

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max files per zip | 500 | Matches existing `MAX_FILES_PER_BATCH` in `batch_import_service.py` |
| Max per-file size | 50 MB | Largest FIT files (12hr ultras with all sensors) are ~30 MB; 50 MB gives headroom |
| Max nesting depth | 5 levels | Prevent zip-in-zip recursion attacks |
| Max compression ratio | 10:1 | Detect zip bombs -- if uncompressed/compressed > 10, reject entry |

**Implementation of safety limits**:
- **File count**: After listing zip entries, reject if `len(entries) > 500` before extracting anything.
- **Per-file size**: Use `ZipInfo.file_size` (uncompressed size) to check BEFORE extraction. Also enforce during read: use streaming read with `zf.open(entry)` and read in 1 MB chunks with a running total, aborting if the total exceeds 50 MB. This prevents relying solely on the (potentially spoofed) zip header.
- **Nesting depth**: Track directory depth of each `ZipInfo.filename` (count path separators). Also detect nested `.zip` files and reject them (do not recursively extract).
- **Compression ratio**: For each entry, compute `ZipInfo.file_size / ZipInfo.compress_size`. If ratio > 10, skip the entry with an error message in the per-file response. Guard against `compress_size == 0` (division by zero).

**Acceptance criteria**:
- `POST /activities/upload` with multiple .fit files returns array of task IDs
- Uploading a .zip containing 3 FIT files creates 3 activities with 3 task IDs
- .zip with non-FIT files returns per-file errors without failing other files
- Duplicate files within zip are detected and reported individually
- Backward-compatible: old `POST /activities/upload-fit` still works
- Zip with >500 files is rejected with a clear error
- Zip entries >50 MB are rejected per-file (streaming size enforcement)
- Nested zips (zip-in-zip) are rejected
- Compression ratio >10:1 entries are flagged and skipped

**Estimated complexity**: M

---

### Plan 8.1.3: Frontend -- Drag-and-Drop Upload Zone

**Description**: Replace the simple file input button with a drag-and-drop zone on the Activities page. Support dropping .fit and .zip files (including multiple files at once). Wire up to the new multi-upload endpoint.

**Files to modify**:
- `frontend/src/components/activities/UploadButton.tsx` -- Major rewrite. Rename to `UploadZone.tsx`. Add drag-and-drop event handlers (`onDragEnter`, `onDragOver`, `onDragLeave`, `onDrop`). Show visual feedback when dragging over. Keep the click-to-browse fallback. Accept multiple files. Call new multi-upload API function.
- `frontend/src/components/activities/UploadButton.css` -- Rename to `UploadZone.css`. Add drop zone styling: dashed border, highlight on drag-over, file list preview.
- `frontend/src/api/activities.ts` -- Add `uploadMultiple(files: File[], onProgress)` function using the new endpoint. Add `uploadFitFiles(files: File[], onProgress)` that handles both single and multi-file scenarios.
- `frontend/src/api/types.ts` -- Add `MultiUploadResponse` interface with `uploads: { filename, activity_id?, task_id?, error? }[]`.
- `frontend/src/pages/ActivityListPage.tsx` -- Update to use `UploadZone` instead of `UploadButton`. Adjust layout to accommodate the drop zone.

**Technical approach**:
- Use native HTML5 Drag and Drop API (no library needed).
- Drop zone appears as a compact button normally, expands to a full drop area when dragging files over the page.
- `dataTransfer.items` gives access to dropped files.
- Filter for `.fit` and `.zip` extensions before uploading.
- Show file list with per-file status (uploading/processing/done/error).
- Axios `onUploadProgress` provides upload percentage for the overall request.

**Acceptance criteria**:
- Dragging files over the Activities page shows a visual drop zone
- Dropping .fit files triggers upload with progress indicator
- Dropping .zip files extracts and processes all FIT files inside
- Dropping multiple files uploads all simultaneously
- Click-to-browse still works as fallback
- Invalid file types show clear error message
- Each file shows individual status (uploading/processing/done/error)

**Estimated complexity**: L

---

### Plan 8.1.4: Frontend -- Real-Time Processing Status with Polling

**Description**: After upload completes (HTTP response received), show a per-file processing status card that polls `GET /tasks/{task_id}` until complete. Display the processing stage and progress bar. When complete, refresh the activity list.

**Files to create**:
- `frontend/src/components/activities/ProcessingStatus.tsx` -- Component showing task progress: stage label, progress bar (0-100%), elapsed time, and final success/error state. Auto-polls task endpoint every 2 seconds.
- `frontend/src/components/activities/ProcessingStatus.css` -- Styling for progress bar, stage labels, success/error states.
- `frontend/src/hooks/useTaskPolling.ts` -- Custom hook: `useTaskPolling(taskId: string)` returns `{ status, progress, stage, error, isComplete }`. Uses `setInterval` with 2-second polling. Stops when status is SUCCESS or FAILURE.

**Files to modify**:
- `frontend/src/api/types.ts` -- Update `TaskStatus` interface to include `progress: number`, `stage: string | null`, `detail: string | null`, `error: string | null`. **NOTE**: The existing `TaskStatus` type (`{ task_id, status, result }`) is already missing the `error` field that the backend returns on failure. This update must add ALL missing fields at once:
  ```typescript
  export interface TaskStatus {
    task_id: string;
    status: string;
    progress: number;
    stage: string | null;
    detail: string | null;
    error: string | null;
    result: unknown;
  }
  ```
  Any existing code referencing `TaskStatus` must be checked for compatibility with the expanded interface.
- `frontend/src/api/activities.ts` -- Add `getTaskStatus(taskId: string)` function.
- `frontend/src/components/activities/UploadZone.tsx` (from 8.1.3) -- After upload response, render `<ProcessingStatus>` for each returned task ID. When all tasks complete, call `onUploadComplete()`.

**Technical approach**:
- Polling with `setInterval` (not WebSocket -- simpler, Celery result backend is already polled via REST).
- 2-second interval balances responsiveness with server load.
- Progress bar uses CSS transitions for smooth animation.
- Stage names from backend map to user-friendly labels: "parsing" -> "Parsing FIT file", "streams" -> "Processing ride data", "laps" -> "Analyzing laps", "metrics" -> "Computing metrics".
- Auto-cleanup: polling stops on unmount (useEffect cleanup).
- When processing finishes successfully, show brief success state then auto-dismiss after 3 seconds.

**Acceptance criteria**:
- After upload, each file shows a processing card with progress bar
- Progress bar advances from 0% to 100% as backend processes the file
- Current stage name displayed (e.g., "Processing ride data... 45%")
- On success: green checkmark, auto-dismisses after 3 seconds, activity list refreshes
- On failure: red error message with detail from backend
- Multiple concurrent uploads each show independent progress
- Polling stops when component unmounts (no memory leaks)

**Estimated complexity**: M

---

## Phase 8.2: Integration Settings & Backfill UI (INSERTED)

**Goal**: Users can connect/disconnect Garmin and Strava accounts from the Settings page, configure backfill time periods, and trigger syncs. Strava OAuth flow works correctly in the browser.

**Requirements**: Feature #1 (Garmin & Strava connection UI)

**Dependencies**: Phase 8

### Plan 8.2.1: Backend -- Configurable Backfill Time Period + Strava OAuth Redirect Fix

**Description**: Add a `backfill_days` parameter to the Garmin sync and Strava backfill endpoints so users can control how far back to sync. Add a backfill endpoint for Garmin (currently only Strava has one). Fix the Strava OAuth callback to redirect browsers to the frontend instead of returning raw JSON.

**Files to modify**:
- `backend/app/routers/integrations.py` -- Add optional `days: int = Query(default=30, ge=1, le=3650)` parameter to `trigger_garmin_sync` and `trigger_strava_backfill`. Pass to Celery task args. Add `POST /integrations/garmin/backfill` endpoint mirroring the Strava backfill pattern. **Fix `strava_callback()`** to return a `RedirectResponse` to the frontend (see below).
- `backend/app/workers/tasks/garmin_sync.py` -- Accept optional `backfill_days: int` arg in `sync_garmin_activities`. Override the lookback window when provided.
- `backend/app/workers/tasks/strava_sync.py` -- Accept optional `backfill_days: int` arg in `strava_historical_backfill`. Use it to set the `after` epoch instead of fetching all activities.
- `backend/app/schemas/integration.py` -- Add `BackfillRequest` schema with `days: int` field.
- `backend/app/config.py` -- Add `FRONTEND_URL: str = "http://localhost:5173"` to the `Settings` class.

**Strava OAuth Callback Redirect Fix** (Critical):

The current `strava_callback` endpoint returns JSON (`StravaCallbackResponse(connected=True, athlete_id=...)`). When Strava redirects the user's browser to this URL after OAuth authorization, the browser shows raw JSON -- a broken user experience.

**Solution (Option A -- HTTP Redirect, recommended by Architect)**:

1. Add `FRONTEND_URL: str = "http://localhost:5173"` to `backend/app/config.py` Settings class.
2. Add `FRONTEND_URL=http://localhost:5173` to `.env.example`.
3. Modify `strava_callback()` in `backend/app/routers/integrations.py`:
   - Add `format: str | None = Query(default=None)` parameter.
   - On success:
     - If `format == "json"`: return the existing `StravaCallbackResponse` (for programmatic/test use).
     - Otherwise: return `RedirectResponse(url=f"{settings.FRONTEND_URL}/settings?strava_connected=true&athlete_id={athlete_id}")`.
   - On failure (StravaAuthError catch block):
     - If `format == "json"`: raise the existing HTTPException.
     - Otherwise: return `RedirectResponse(url=f"{settings.FRONTEND_URL}/settings?strava_error=auth_failed")`.
4. Add `from starlette.responses import RedirectResponse` import.
5. Update the endpoint's `response_model` to `None` (since it now returns a redirect, not JSON). Keep `response_model=StravaCallbackResponse` only in the `format=json` code path via manual return.
6. Update `StravaConnect.tsx` (Plan 8.2.2) to read `strava_connected` and `strava_error` query params from the URL on mount and display appropriate success/error state.

**Technical approach (Backfill)**:
- Garmin backfill: reuse `sync_garmin_activities` with a forced lookback override. The existing logic already fetches since a date; we just control that date.
- Strava backfill: `strava_historical_backfill` currently fetches ALL activities. Add `after_epoch` parameter to limit the time window.
- Default to 30 days if not specified (same as current behavior).
- Maximum 3650 days (10 years) to prevent unreasonable requests.

**Acceptance criteria**:
- `POST /integrations/garmin/sync?days=90` syncs last 90 days of Garmin activities
- `POST /integrations/garmin/backfill?days=365` creates a backfill task for 1 year
- `POST /integrations/strava/backfill?days=180` limits backfill to 6 months
- Default behavior unchanged when `days` parameter omitted
- Parameter validation rejects days < 1 or > 3650
- **Strava OAuth redirect**: Browser visiting `/integrations/strava/callback?code=xxx` redirects to `http://localhost:5173/settings?strava_connected=true&athlete_id=12345` on success
- **Strava OAuth error redirect**: Auth failure redirects to `http://localhost:5173/settings?strava_error=auth_failed`
- **JSON fallback**: `GET /integrations/strava/callback?code=xxx&format=json` still returns JSON `StravaCallbackResponse` (for tests and programmatic use)
- `FRONTEND_URL` setting is documented in `.env.example`

**Estimated complexity**: M

---

### Plan 8.2.2: Frontend -- Integrations Section on Settings Page

**Description**: Add Garmin and Strava connection panels to the Settings page. Garmin shows email/password form; Strava shows OAuth2 "Connect with Strava" button. Both show connection status, last sync time, and disconnect option. Strava handles OAuth redirect query parameters.

**Files to modify**:
- `frontend/src/pages/SettingsPage.tsx` -- Add two new sections below the FTP card: "Garmin Connect" and "Strava". Each section shows connected/disconnected state and appropriate actions.

**Files to create**:
- `frontend/src/components/settings/GarminConnect.tsx` -- Component with: if disconnected, show email/password form + "Connect" button; if connected, show status (active/error), last sync time, "Sync Now" button, "Disconnect" button.
- `frontend/src/components/settings/GarminConnect.css` -- Styling for connection card.
- `frontend/src/components/settings/StravaConnect.tsx` -- Component with: if disconnected, show "Connect with Strava" button (opens OAuth URL in same window -- Strava redirects back to our backend which redirects to frontend). If connected, show athlete ID, last sync time, "Sync Now" button, "Disconnect" button. **On mount**: check URL query params for `strava_connected=true` (show success toast, clear param) or `strava_error=auth_failed` (show error message, clear param). Use `useSearchParams()` from React Router.
- `frontend/src/components/settings/StravaConnect.css` -- Styling with Strava brand orange.
- `frontend/src/api/integrations.ts` -- API functions: `connectGarmin(email, password)`, `getGarminStatus()`, `disconnectGarmin()`, `triggerGarminSync(days?)`, `triggerGarminBackfill(days?)`, `getStravaAuthUrl()`, `getStravaStatus()`, `disconnectStrava()`, `triggerStravaSync()`, `triggerStravaBackfill(days?)`.
- `frontend/src/api/types.ts` -- Add interfaces: `IntegrationStatus`, `StravaStatus`, `GarminConnectRequest`, `SyncResponse`.

**Technical approach**:
- Garmin: simple POST to `/integrations/garmin/connect` with email/password. Backend validates credentials immediately and returns success/failure.
- Strava OAuth flow (revised for redirect):
  1. User clicks "Connect with Strava" on Settings page.
  2. Frontend calls `GET /integrations/strava/authorize` to get the OAuth URL.
  3. Frontend navigates to the Strava OAuth URL (`window.location.href = url`).
  4. User authorizes on Strava's site.
  5. Strava redirects browser to `GET /integrations/strava/callback?code=xxx`.
  6. Backend exchanges code for tokens, stores integration, then returns `RedirectResponse` to `http://localhost:5173/settings?strava_connected=true&athlete_id=12345`.
  7. Browser loads Settings page. `StravaConnect.tsx` reads query params on mount, shows success toast, clears params from URL with `setSearchParams()`.
- Status polling after "Sync Now": show spinner, poll task status until complete, then refresh integration status.

**Acceptance criteria**:
- Settings page shows Garmin section with connect/disconnect functionality
- Settings page shows Strava section with OAuth connect flow
- After Strava OAuth redirect, Settings page shows success message and connected state
- Strava OAuth error redirects show appropriate error message
- Connected integrations show green "Active" badge and last sync time
- Error integrations show red "Error" badge with error message
- "Sync Now" button triggers sync and shows progress
- "Disconnect" button shows confirmation dialog then disconnects
- Password field is masked and never stored in frontend state after submission

**Estimated complexity**: L

---

### Plan 8.2.3: Frontend -- Backfill Configuration UI

**Description**: Add a backfill configuration panel within each integration card. Users can select a time period (30 days, 90 days, 6 months, 1 year, 2 years, all time) and trigger a backfill. Show backfill progress.

**Files to modify**:
- `frontend/src/components/settings/GarminConnect.tsx` -- Add "Backfill" section below sync controls: dropdown/radio for time period, "Start Backfill" button, progress display.
- `frontend/src/components/settings/StravaConnect.tsx` -- Same backfill section.
- `frontend/src/api/integrations.ts` -- Backfill API functions already defined in 8.2.2; ensure `days` parameter is passed.

**Files to create**:
- `frontend/src/components/settings/BackfillSelector.tsx` -- Reusable component: time period dropdown/radio group + "Start Backfill" button + task progress display. Props: `onBackfill(days: number)`, `taskId: string | null`.

**Technical approach**:
- Predefined time periods: `[{ label: 'Last 30 days', days: 30 }, { label: 'Last 90 days', days: 90 }, { label: 'Last 6 months', days: 180 }, { label: 'Last year', days: 365 }, { label: 'Last 2 years', days: 730 }, { label: 'All time', days: 3650 }]`.
- After triggering backfill, show the same `ProcessingStatus` component (or reuse `useTaskPolling` hook from Plan 8.1.4) to display progress.
- Disable the backfill button while a backfill is in progress.
- Show warning for large backfills ("This may take several minutes").

**Acceptance criteria**:
- Each integration card has a "Backfill" section with time period selector
- Selecting "Last 90 days" and clicking "Start Backfill" triggers backfill for 90 days
- Backfill progress is shown with the same polling mechanism as upload processing
- Button is disabled while backfill is running
- Completion shows summary (X activities synced, Y skipped)

**Estimated complexity**: M

---

## Phase 8.3: Unit System & Calendar Improvements (INSERTED)

**Goal**: Users can switch between metric and US (imperial) units globally, and navigate the calendar with infinite scroll.

**Requirements**: Feature #3 (unit conversion), Feature #6 (calendar infinite scroll)

**Dependencies**: Phase 8

### Plan 8.3.1: Backend -- Unit System Setting

**Description**: Add a `unit_system` field to the user settings model and API, allowing users to store their preference for "metric" or "imperial".

**Files to modify**:
- `backend/app/models/user_settings.py` -- Add `unit_system: Mapped[str] = mapped_column(String(20), server_default="metric", nullable=False)`.
- `backend/app/schemas/settings.py` -- Add `unit_system: str` to `UserSettingsResponse` and `unit_system: str | None` to `UserSettingsUpdate`. Validate against `{"metric", "imperial"}`.
- `backend/app/routers/settings.py` -- Handle `unit_system` in `update_settings()`. Add validation.
- `backend/alembic/versions/` -- New migration adding `unit_system` column with default "metric".

**Technical approach**:
- Backend stores preference only. All data remains in metric (SI units) in the database.
- Conversion is purely a frontend concern.
- Simple column addition with server_default so existing rows get "metric".

**Acceptance criteria**:
- `GET /settings` returns `unit_system: "metric"` by default
- `PUT /settings` with `{ "unit_system": "imperial" }` persists the preference
- Invalid values (e.g., "banana") return 400 error
- Migration runs without data loss

**Estimated complexity**: S

---

### Plan 8.3.2: Frontend -- Unit Conversion System

**Description**: Build a global unit conversion system using React Context + custom hooks. Update all components that display distance, elevation, weight, or temperature to use the conversion system.

**Files to create**:
- `frontend/src/contexts/UnitContext.tsx` -- React Context providing `{ unitSystem: 'metric' | 'imperial', setUnitSystem }`. Loads from user settings API on mount. Persists changes via `PUT /settings`.
- `frontend/src/hooks/useUnits.ts` -- Custom hook returning conversion functions and unit labels: `{ formatDistance(meters), formatElevation(meters), formatWeight(kg), formatTemperature(celsius), formatSpeed(mps), distanceUnit, elevationUnit, weightUnit, tempUnit, speedUnit }`.
- `frontend/src/utils/conversions.ts` -- Pure conversion functions: `metersToKm`, `metersToMiles`, `metersToFeet`, `kgToLbs`, `celsiusToFahrenheit`, `mpsToKph`, `mpsToMph`. All functions handle null input gracefully.

**Files to modify**:
- `frontend/src/utils/format.ts` -- Remove hardcoded metric assumptions from `formatDistance` and `formatElevation`. These become unit-aware via the hook, or the raw formatters become "format number" utilities called by the hook.
- `frontend/src/App.tsx` (or root component) -- Wrap app in `<UnitProvider>`.
- **Components to update** (replace hardcoded "km"/"m" with hook values):
  - `frontend/src/components/activities/ActivityTable.tsx` -- Distance column header: "km" -> `distanceUnit`
  - `frontend/src/components/activities/ActivityStats.tsx` -- Distance unit "km" -> `distanceUnit`, elevation "m" -> `elevationUnit`
  - `frontend/src/components/dashboard/TrainingSummary.tsx` -- Distance "km" -> `distanceUnit`
  - `frontend/src/components/calendar/WeeklySummary.tsx` -- Distance label
  - `frontend/src/components/charts/TotalsSummaryCards.tsx` -- Distance/elevation labels
  - `frontend/src/components/charts/TotalsBarChart.tsx` -- Axis labels
  - `frontend/src/components/charts/FitnessChart.tsx` -- If it shows distance
  - `frontend/src/pages/SettingsPage.tsx` -- Weight display "kg" -> `weightUnit`

**NOTE**: `TimelineChart.tsx` is NOT included in this update list. It only displays Power (W) and Heart Rate (bpm) axes -- neither of which requires unit conversion. Power is always watts, heart rate is always bpm regardless of metric/imperial setting.

**Technical approach**:
- Context provides the current unit system. Hook provides formatted output.
- Usage pattern in components: `const { formatDistance, distanceUnit } = useUnits();` then `{formatDistance(meters)} {distanceUnit}`.
- Conversion factors: 1 km = 0.621371 mi, 1 m = 3.28084 ft, 1 kg = 2.20462 lbs, C to F = C * 9/5 + 32.
- Speed: metric = km/h, imperial = mph.
- All backend data stays in SI. Conversion is display-only.
- Context syncs with backend settings on load and on change.

**Acceptance criteria**:
- Switching to "Imperial" in settings changes all distances to miles, elevation to feet, weight to lbs
- Switching back to "Metric" restores km, m, kg
- All numeric displays use correct conversion factors
- Unit labels update dynamically (column headers, stat cards, chart axes)
- Page refresh preserves the preference (loaded from backend)
- Null/missing values still display "--" regardless of unit system

**Estimated complexity**: L

---

### Plan 8.3.3: Frontend -- Unit Toggle on Settings Page

**Description**: Add a unit system toggle to the Settings page, allowing users to switch between Metric and US/Imperial.

**Files to modify**:
- `frontend/src/pages/SettingsPage.tsx` -- Add a "Units" section with two radio buttons or a toggle: "Metric (km, m, kg, C)" and "Imperial (mi, ft, lbs, F)". Wire to the UnitContext's `setUnitSystem`.

**Technical approach**:
- Simple radio group or segmented control.
- onChange calls `setUnitSystem('imperial')` which updates context AND fires `PUT /settings` with `{ unit_system: 'imperial' }`.
- Show a brief success toast on save.

**Acceptance criteria**:
- Settings page shows "Units" section with Metric/Imperial toggle
- Changing the toggle immediately updates all displayed units site-wide
- Preference persists across page refreshes
- Default is "Metric" for new users

**Estimated complexity**: S

---

### Plan 8.3.4: Frontend -- Calendar Infinite Scroll

**Description**: Replace the prev/next button navigation on the Calendar page with an infinite scroll implementation. Loading older months scrolls down, newer months scroll up.

**Files to modify**:
- `frontend/src/pages/CalendarPage.tsx` -- Major rewrite. Replace single-month state with an array of loaded months. Use `IntersectionObserver` to detect when the user scrolls near the top or bottom sentinel elements. Load adjacent months when sentinels become visible.
- `frontend/src/pages/CalendarPage.css` -- Update layout for vertical scrollable container with multiple months.
- `frontend/src/components/calendar/CalendarNavigation.tsx` -- Simplify or repurpose: add a "Today" button that scrolls back to the current month. Keep month/year label as a sticky header.

**Files to create**:
- `frontend/src/hooks/useInfiniteCalendar.ts` -- Custom hook managing the array of loaded months, scroll position, and IntersectionObserver setup. Returns `{ months: CalendarMonth[], topRef, bottomRef, scrollToToday, isLoadingOlder, isLoadingNewer }`.

**Technical approach**:
- Start with current month visible, preload 1 month before and 1 after.
- Two `IntersectionObserver` sentinels: one at top (triggers older month load), one at bottom (triggers newer month load).
- Maintain scroll position when prepending months (save scrollHeight before, restore after insert).
- Cap at ~24 months loaded (remove oldest/newest when exceeding to prevent memory issues).
- Each month renders as a `MonthView` component with a sticky year-month header.
- "Today" button scrolls current month into view using `scrollIntoView({ behavior: 'smooth' })`.
- Keep prev/next buttons as alternative navigation (but infinite scroll is the primary interaction).

**Sticky month header -- determining which month label to show**:

When multiple months are partially visible in the scroll container, the sticky header must display the correct month label. Use `IntersectionObserver` on each month heading element:

1. Assign a `ref` to each `<MonthView>`'s heading element (e.g., `<h2 data-month="2025-03">`).
2. Create a separate `IntersectionObserver` with `threshold: [0, 0.1, 0.5, 1.0]` and `rootMargin: '-48px 0px 0px 0px'` (offset by sticky header height) targeting ALL month headings.
3. In the observer callback, track which month headings are currently intersecting and their `boundingClientRect.top` values.
4. The active sticky header month = the last heading whose `top` is <= the sticky header position (i.e., the heading that has scrolled past or is at the sticky bar). This is the topmost month currently visible.
5. Update a `activeMonth` state that drives the sticky header text.
6. When no headings are intersecting above the sticky position (edge case during fast scroll), fall back to the first month in the loaded array whose content is partially visible.

This approach avoids expensive `scroll` event listeners and leverages the browser's optimized `IntersectionObserver` for smooth, jank-free updates.

**Acceptance criteria**:
- Calendar shows current month on load
- Scrolling down loads older months automatically
- Scrolling up loads newer months (if not at current month)
- No flicker or scroll jump when new months load
- "Today" button scrolls to current month
- Maximum 24 months in DOM at any time
- Loading spinners show while fetching month data
- Month headers are sticky within scroll container
- Sticky header correctly shows the topmost visible month when multiple months are in view

**Estimated complexity**: L

---

## Phase 8.4: Dark Mode & UI Modernization (INSERTED)

**Goal**: Users can toggle between light and dark themes. The overall UI is modernized with improved visual hierarchy, consistent spacing, and polished components.

**Requirements**: Feature #7 (dark/light mode + UI modernization)

**Dependencies**: Phase 8 (and benefits from 8.1-8.3 being complete, so new components also get styled)

### Plan 8.4.1: Backend -- Theme Preference Setting

**Description**: Add a `theme` field to user settings for persisting the dark/light mode preference.

**Files to modify**:
- `backend/app/models/user_settings.py` -- Add `theme: Mapped[str] = mapped_column(String(20), server_default="light", nullable=False)`.
- `backend/app/schemas/settings.py` -- Add `theme: str` to `UserSettingsResponse` and `theme: str | None` to `UserSettingsUpdate`. Validate against `{"light", "dark", "system"}`.
- `backend/app/routers/settings.py` -- Handle `theme` in `update_settings()`.
- `backend/alembic/versions/` -- New migration adding `theme` column with default "light".

**Technical approach**:
- Three options: "light", "dark", "system" (follows OS preference via `prefers-color-scheme`).
- Same pattern as unit_system: backend stores preference, frontend applies.

**Acceptance criteria**:
- `GET /settings` returns `theme: "light"` by default
- `PUT /settings` with `{ "theme": "dark" }` persists preference
- "system" option is accepted and stored
- Invalid values return 400 error

**Estimated complexity**: S

---

### Plan 8.4.2: Frontend -- Theme System with CSS Custom Properties

**Description**: Create a complete dark theme by defining dark-mode CSS custom property overrides. Build a ThemeProvider context that applies the correct theme class to the document root.

**Files to modify**:
- `frontend/src/styles/variables.css` -- Add `[data-theme="dark"]` selector with dark color overrides for ALL existing CSS variables. Dark palette: dark backgrounds (#0f1117, #1a1d27, #242731), light text (#e5e7eb, #9ca3af), adjusted accent colors for contrast.

**Files to create**:
- `frontend/src/contexts/ThemeContext.tsx` -- React Context providing `{ theme: 'light' | 'dark' | 'system', setTheme, resolvedTheme: 'light' | 'dark' }`. On mount: load from settings API. Apply theme by setting `document.documentElement.setAttribute('data-theme', resolvedTheme)`. For "system": use `window.matchMedia('(prefers-color-scheme: dark)')` and listen for changes.
- `frontend/src/hooks/useTheme.ts` -- Convenience hook wrapping `useContext(ThemeContext)`.

**Files to modify**:
- `frontend/src/App.tsx` (or root) -- Wrap app in `<ThemeProvider>`.
- `frontend/src/styles/variables.css` -- The dark overrides (detailed above).

**Technical approach**:
- CSS custom properties already power the entire UI. Dark mode only requires overriding the values under `[data-theme="dark"]`.
- Dark color mapping:
  - `--color-bg`: #0f1117
  - `--color-bg-card`: #1a1d27
  - `--color-bg-sidebar`: #0d0f14 (even darker)
  - `--color-bg-input`: #242731
  - `--color-bg-hover`: #2a2d3a
  - `--color-text`: #e5e7eb
  - `--color-text-secondary`: #9ca3af
  - `--color-border`: #2d3041
  - `--color-border-focus`: #3b82f6 (keep primary blue)
  - Shadows: use rgba with higher opacity for visibility on dark backgrounds.
  - Alert backgrounds: darker, semi-transparent versions.
- "system" uses `matchMedia` listener for OS theme changes, updating in real-time.
- Persist to backend on change, with immediate local application (no waiting for API).

**Acceptance criteria**:
- `[data-theme="dark"]` applied to `<html>` element toggles the entire UI to dark mode
- All text is readable against dark backgrounds (WCAG AA contrast ratio)
- All cards, inputs, buttons, alerts adapt correctly
- Sidebar, topbar, charts, maps, modals all render correctly in both themes
- "system" mode follows OS preference and updates live
- No hardcoded colors outside CSS variables (audit pass)
- No flash of wrong theme on page load (theme applied before render)

**Estimated complexity**: M

---

### Plan 8.4.3: Frontend -- Theme Toggle in UI

**Description**: Add a theme toggle control to the topbar (always visible) and to the Settings page (full options). Topbar shows a sun/moon icon toggle; Settings shows light/dark/system radio group.

**Files to modify**:
- `frontend/src/components/Layout.tsx` -- Add a theme toggle icon button in the `topbar-right` area, before the user name. Sun icon for light, moon icon for dark. Click cycles through: light -> dark -> system -> light.
- `frontend/src/components/Layout.css` -- Style the theme toggle button.
- `frontend/src/pages/SettingsPage.tsx` -- Add "Appearance" section with three radio options: Light, Dark, System (follows device). Show visual preview thumbnails if feasible.

**Technical approach**:
- Topbar toggle: simple icon button. Use inline SVGs for sun (light mode active) and moon (dark mode active) and monitor (system mode active) icons. Keep it minimal: 24x24px, no border, subtle hover effect.
- Settings page: three-option radio group with descriptions ("Light - always use light theme", "Dark - always use dark theme", "System - match your device settings").
- Both controls update the same ThemeContext, which syncs to backend.

**Acceptance criteria**:
- Topbar shows theme toggle icon (sun/moon/monitor)
- Clicking topbar toggle cycles through themes
- Settings page shows Appearance section with all three options
- Both controls are in sync (changing one updates the other)
- Theme persists across page refreshes and sessions

**Estimated complexity**: S

---

### Plan 8.4.4: Frontend -- UI Modernization Pass

**Description**: Comprehensive visual polish across the application. Improve typography, spacing, card designs, table styling, form elements, and overall visual hierarchy. This is a design-focused plan that touches many CSS files.

**Files to modify**:
- `frontend/src/styles/variables.css` -- Refine spacing scale, add `--space-3xl: 4rem`. Add `--font-size-*` scale (xs through 2xl). Add `--font-weight-*` tokens. Add `--letter-spacing-*` tokens.
- `frontend/src/styles/global.css` -- Upgrade base styles:
  - Better default link styles with underline-offset
  - Improved button hover/active states with subtle transform (`translateY(-1px)`)
  - Card hover state with elevated shadow
  - Input focus ring improvement (offset ring instead of box-shadow)
  - Smooth transitions on all interactive elements
  - Better scrollbar styling (thin, subtle)
  - Improved alert component with icon slots
- `frontend/src/components/Layout.css` -- Sidebar improvements: subtle gradient background, icon support for nav links (prep icons but text-only OK for now), improved brand area, smooth sidebar transitions. Topbar: subtle bottom shadow, cleaner right-side layout.
- `frontend/src/components/activities/ActivityTable.css` -- Alternating row colors, hover highlight, improved header styling with uppercase labels, better number alignment.
- `frontend/src/components/activities/ActivityStats.css` -- Stat cards with subtle gradient top border (power=blue, hr=red, etc.), improved value/label hierarchy.
- `frontend/src/pages/CalendarPage.css` -- Improved day cell styling with smoother color transitions, better TSS intensity colors for both light and dark themes.
- `frontend/src/components/calendar/MonthView.css` -- Cleaner grid lines, improved day header row.
- `frontend/src/pages/ActivityListPage.css` -- Better page header layout, improved empty state.
- `frontend/src/components/dashboard/*.css` -- Dashboard widget improvements: better card headers, consistent widget heights, improved chart container styling.
- `frontend/src/components/charts/*.css` -- Chart container improvements: better legend placement, responsive sizing, loading states.

**Technical approach**:
- No structural changes -- purely CSS improvements using existing CSS custom properties.
- Key principles:
  1. **Consistent spacing**: Use the spacing scale everywhere (no arbitrary pixel values).
  2. **Visual hierarchy**: Larger/bolder for primary info, smaller/muted for secondary.
  3. **Subtle animations**: hover transitions on cards (shadow lift), buttons (slight scale), nav links (color fade).
  4. **Better typography**: Tighter letter-spacing on headers, comfortable line-height on body text.
  5. **Professional color usage**: Muted backgrounds, strong accents only for interactive elements.
  6. **Improved data density**: Tables show more info in less space with better scanning patterns.
- All improvements must work in BOTH light and dark themes.
- No JavaScript changes -- CSS only.

**Acceptance criteria**:
- All pages look visually cohesive and professional
- Consistent spacing and typography throughout
- Interactive elements have smooth hover/focus transitions
- Tables are easy to scan with alternating rows and clear headers
- Cards feel elevated with proper shadow and border treatment
- Both light and dark themes look polished (not just "working")
- No regressions: all existing functionality preserved
- Responsive: desktop (>1200px) looks great, tablet (768-1200px) is usable

**Estimated complexity**: L

---

## Cross-Phase Concerns

### Shared Patterns

**Task Polling**: Plans 8.1.4 and 8.2.3 both need task progress polling. The `useTaskPolling` hook (created in 8.1.4) should be the single implementation reused in 8.2.3 for backfill progress.

**Settings Infrastructure**: Plans 8.3.1 (unit_system), 8.4.1 (theme), and the existing settings all share the same `UserSettings` model and API. The Alembic migrations should be created in sequence: 8.3.1's migration first, then 8.4.1's migration.

**CSS Variables**: Phase 8.4 adds dark mode overrides to `variables.css`. All CSS written in phases 8.1-8.3 must use CSS custom properties (not hardcoded colors) to automatically support dark mode.

### Testing Strategy

**Backend tests**:
- Phase 8.1: Test granular progress reporting in Celery tasks (mock `self.update_state`). Test multi-file upload endpoint with fixtures. Test zip extraction edge cases (>500 files, >50MB file, nested zips, compression ratio >10:1).
- Phase 8.2: Test backfill `days` parameter validation and passing to Celery tasks. Test Strava callback redirect (both browser redirect and `?format=json` paths). Test `FRONTEND_URL` config loading.
- Phase 8.3: Test `unit_system` setting validation and persistence.
- Phase 8.4: Test `theme` setting validation and persistence.

**Frontend tests** (if test framework is set up):
- Unit tests for `conversions.ts` functions.
- Hook tests for `useTaskPolling`, `useInfiniteCalendar`.
- Component tests for drag-and-drop behavior.

**Manual QA checklist** (per phase):
- [ ] All new components render correctly
- [ ] API calls succeed and error states are handled
- [ ] Loading states are shown during async operations
- [ ] Dark and light modes both work (after Phase 8.4)
- [ ] No console errors or warnings

### Migration Safety

All Alembic migrations add nullable or server-defaulted columns. No destructive changes. Migrations can be run on a live database without downtime.

### Commit Strategy

Each plan maps to 1-2 commits:
- Plan 8.1.1: `feat(backend): add granular Celery task progress reporting`
- Plan 8.1.2: `feat(backend): add multi-file upload endpoint with zip support`
- Plan 8.1.3: `feat(frontend): add drag-and-drop upload zone on activities page`
- Plan 8.1.4: `feat(frontend): add real-time processing status with task polling`
- Plan 8.2.1: `feat(backend): add configurable backfill period and fix Strava OAuth redirect`
- Plan 8.2.2: `feat(frontend): add Garmin and Strava connection UI to settings`
- Plan 8.2.3: `feat(frontend): add backfill configuration with progress display`
- Plan 8.3.1: `feat(backend): add unit_system setting to user preferences`
- Plan 8.3.2: `feat(frontend): add global unit conversion system with context and hooks`
- Plan 8.3.3: `feat(frontend): add unit toggle to settings page`
- Plan 8.3.4: `feat(frontend): add infinite scroll to training calendar`
- Plan 8.4.1: `feat(backend): add theme preference setting`
- Plan 8.4.2: `feat(frontend): add dark theme with CSS custom property overrides`
- Plan 8.4.3: `feat(frontend): add theme toggle to topbar and settings`
- Plan 8.4.4: `feat(frontend): modernize UI with improved typography, spacing, and polish`

### Success Criteria (Phase-Level)

**Phase 8.1 is DONE when**:
1. Users can drag-and-drop .fit/.zip files onto the activities page
2. Upload progress bar shows real HTTP upload percentage
3. After upload, processing progress bar shows real backend progress (parsing, streams, metrics)
4. Multiple concurrent uploads each show independent progress
5. Processing completion auto-refreshes the activity list

**Phase 8.2 is DONE when**:
1. Settings page shows Garmin connection form (email/password)
2. Settings page shows Strava OAuth "Connect" button
3. Strava OAuth flow redirects back to Settings page with success/error state (no raw JSON)
4. Connected integrations show status, last sync, and sync/disconnect controls
5. Users can configure backfill time period (30d, 90d, 6mo, 1yr, 2yr, all)
6. Backfill progress is displayed in real time

**Phase 8.3 is DONE when**:
1. Settings page has Metric/Imperial toggle
2. Switching to Imperial shows miles, feet, lbs, F everywhere
3. Switching to Metric shows km, m, kg, C everywhere
4. Preference persists across sessions
5. Calendar supports infinite scroll (no more prev/next-only navigation)
6. "Today" button returns to current month
7. Sticky month header correctly reflects the topmost visible month

**Phase 8.4 is DONE when**:
1. Dark mode toggle in topbar works instantly
2. Settings page offers Light/Dark/System theme options
3. All pages, components, charts, and modals render correctly in dark mode
4. UI feels modern: consistent spacing, smooth transitions, professional typography
5. Both light and dark themes look polished and cohesive
