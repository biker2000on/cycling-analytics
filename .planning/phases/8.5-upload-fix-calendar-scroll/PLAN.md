# Phase 8.5: FIT Upload Debugging & Calendar Infinite Scroll Fix

**Goal**: Fix two UX-critical bugs: (1) .zip file uploads not properly tracked/displayed in UI, and (2) calendar infinite scroll broken in both directions.

**Dependencies**: Phase 8.4

**UI Constraint**: No standard browser `alert()`/`confirm()` dialogs anywhere. Use sweetalert2 (or equivalent styled modal library) for all confirmations, warnings, and error messages.

## Issue Analysis

### Issue 1: ZIP Upload Decoding
The backend zip handling is solid (extraction, safety limits, Celery queuing all work). The critical bug is a **frontend filename mismatch**: when uploading `rides.zip`, the backend returns `FileUploadResult` entries with filenames from *inside* the zip (e.g., `ride_a.fit`), but the frontend matches by `file.name` (the zip filename) at `UploadZone.tsx:93-94`. This never matches, so zip uploads silently show "Done" with no error feedback or task tracking.

Additionally, one test .zip file (`21817961064.zip`) contains a nested zip which the backend correctly rejects — this should surface as a warning to the user.

### Issue 2: Calendar Infinite Scroll
Five bugs identified in `useInfiniteCalendar.ts` and `CalendarPage.tsx`:
1. **Observer root wrong** (`CalendarPage.tsx:22-29`): IntersectionObserver uses viewport instead of scroll container
2. **No scroll preservation on prepend**: After loading an older month, content shifts down pushing the top sentinel out of view — never triggers again
3. **Future month guard too strict** (`useInfiniteCalendar.ts:152-156`): Initial state includes `currentMonth+1`, but `loadNewer` blocks anything `> currentMonth`, so bottom scroll never adds months
4. **Sentinels too small** (`CalendarPage.css:42-45`): 1px height with `visibility: hidden` is fragile for intersection detection
5. **Dual useEffect** (`useInfiniteCalendar.ts:105-120`): Two overlapping fetch effects — only the second (line 114) is needed

## Plans

### Plan 8.5.1: Backend — Add source_file Field to Upload Response
*Prerequisite for Plan 8.5.2 — required for correct multi-zip attribution.*

- Add `source_file: str | None = None` to `FileUploadResult` schema (`backend/app/schemas/activity.py:93-99`)
- In `import_service.handle_zip_upload()` (`import_service.py:247-254`), set `source_file` to the zip's original filename for each extracted `FileUploadResult`
- In `import_service.handle_multi_upload()`, set `source_file` to original filename for direct .fit uploads too
- Default `None` for backward compatibility
- Update `FileUploadResult` TypeScript type in `frontend/src/api/types.ts`
- Add test: upload a zip, verify response includes `source_file` matching the zip filename

### Plan 8.5.2: Frontend — Fix UploadZone ZIP Result Mapping
**Depends on**: Plan 8.5.1 (needs `source_file` field for correct multi-zip attribution)

**Install sweetalert2**: Add `sweetalert2` as a dependency. Replace any existing `window.confirm()` / `window.alert()` calls (e.g., reprocess confirmation in `ActivityDetailPage.tsx`) with sweetalert2 modals. Use sweetalert2 for upload error/warning toasts.

**Data model change** — extend `FileUploadState` with a tree structure for zip entries:
```typescript
interface ExtractedFileState {
  filename: string;
  status: 'processing' | 'done' | 'error';
  taskId?: string;
  activityId?: number;
  error?: string;
}

interface FileUploadState {
  file: File;
  status: 'waiting' | 'uploading' | 'processing' | 'done' | 'error';
  progress: number;
  taskId?: string;       // for direct .fit uploads
  activityId?: number;
  error?: string;
  children?: ExtractedFileState[];  // for .zip uploads
}
```

**Result mapping rewrite** (`UploadZone.tsx:90-115`):
- Match direct `.fit` results by `u.source_file === fs.file.name` or `u.filename === fs.file.name`
- For `.zip` files: collect all results where `u.source_file === fs.file.name` into `children` array
- Show nested results in UI: "rides.zip → ride_a.fit (Processing), ride_b.fit (Done)"
- Surface nested zip rejection errors from children with `error` field set

**Polling scalability**: Cap concurrent `ProcessingStatus` polling at 10 instances. Use a client-side queue: start polling the first 10 tasks; as each completes (done/error), start polling the next from the queue.

**Completion callback**: `onUploadComplete` fires once when ALL children (or direct files) reach terminal state (done or error). Replace the current `setTimeout` at line 122-124 with a status-aggregate check.

### Plan 8.5.3: Frontend — Fix Calendar Infinite Scroll (All Bugs)
*Atomic change merging all 5 calendar fixes — they cannot be independently tested.*

**Fix observer root** (`CalendarPage.tsx:22-29, 40-48`):
- Set `root: scrollContainerRef.current` on both top and bottom IntersectionObservers
- Ensures intersection detection happens relative to the scroll container, not the viewport

**Fix sentinel CSS** (`CalendarPage.css:42-45`):
- Change from `height: 1px; visibility: hidden` to `height: 20px; pointer-events: none`

**Fix future guard** (`useInfiniteCalendar.ts:47-57, 144-172`):
- Remove `next` month from initial state: initialize with `[prev, current]` only
- Change guard condition using `incrementMonth` helper:
  ```
  const limit = incrementMonth(currentYear, currentMonth);
  if (newerMonth.year > limit.year ||
      (newerMonth.year === limit.year && newerMonth.month > limit.month)) {
    return prev;
  }
  ```
- This allows loading exactly one month into the future but no further

**Scroll position preservation on prepend**:
- In the top sentinel's IntersectionObserver callback (CalendarPage.tsx), BEFORE calling `loadOlder()`: store `container.scrollHeight` in a ref (`prevScrollHeightRef`)
- Add a `useLayoutEffect` that depends on `getMonthKey(months[0]?.year, months[0]?.month)` — when the first month changes, compute `newScrollHeight - prevScrollHeight` and add delta to `container.scrollTop`
- This keeps the user's visual position stable so the top sentinel exits view and can trigger again on the next scroll-up

**Race condition protection**:
- Add a `pendingMonths` Set ref to prevent duplicate month entries when `loadOlder`/`loadNewer` fire rapidly before the first render commits

**Merge dual useEffect** (`useInfiniteCalendar.ts:105-120`):
- Remove the first useEffect (lines 105-111) — the second (lines 114-120) handles all cases since new months are always created with `loading: true`

**Verification**:
- Scrolling up continuously loads older months without jumping (no limit until MAX_MONTHS cap)
- Scrolling down loads months up to one month ahead of current, then stops
- Rapid scrolling does not create duplicate months
- "Today" button scrolls to current month
- MAX_MONTHS (24) cap trims from the opposite end when exceeded

### Plan 8.5.4: E2E Playwright Test — Upload .zip Files and Verify

**Infrastructure setup** (no existing Playwright setup in project):
- Install `@playwright/test` as dev dependency in frontend
- Create `playwright.config.ts` with baseURL `http://localhost:5173`
- Configure to assume dev servers are running (no auto-start — requires `podman compose`, backend, frontend, Celery all running)

**Test implementation**:
- Read credentials from `.env.test` at project root — variables are `LOCAL_USER` (email) and `LOCAL_PASSWORD` — never hardcode in test files
- Log in via the frontend login page
- Navigate to Activities page
- Upload the 4 .zip files from project root `.fitfiles/` directory (use absolute path resolved from project root, not relative from frontend/)
- Verify each zip's extracted .fit files appear in the upload status UI
- Wait for Celery processing to complete (poll status indicators)
- Verify activities appear in the activity list with correct metadata (power, HR, duration)
- Navigate to calendar and verify rides appear on correct dates
- Test calendar infinite scroll: scroll up past ride dates, verify continuous loading; scroll down to current month

**Runtime dependencies**: Requires Podman services (TimescaleDB, Redis), backend on :8000, frontend on :5173, Celery worker — all must be running before test execution.

## Success Criteria
1. Uploading .zip files shows per-extracted-file progress and status in the UI
2. Uploading two .zip files simultaneously correctly attributes extracted files to their respective parent zips
3. All 4 test .zip files successfully process and appear in the activity list
4. Nested zip warning surfaces to user via styled modal (not browser alert)
5. Calendar infinite scroll works continuously in both directions
6. Scroll position is preserved when loading older months (no visual jump)
7. Future months load up to one month ahead, then stop
8. "Today" button scrolls to current month
9. No standard `alert()`/`confirm()` dialogs anywhere — all use sweetalert2
10. E2E Playwright test passes for full upload + calendar workflow
