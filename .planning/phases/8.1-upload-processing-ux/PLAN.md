# Phase 8.1: Upload & Processing UX

**Goal**: Users see real-time progress during file upload AND backend processing, with drag-and-drop support on the Activities page.

**Requirements**: Drag-and-drop upload (#2), Upload progress fix (#4), Post-upload processing status (#5)

**Dependencies**: Phase 8

## Plans

### Plan 8.1.1: Backend -- Granular Celery Task Progress
- Add `self.update_state()` calls to fit_import, garmin_sync, strava_sync tasks
- Update task_service.py to read custom state metadata from `result.info`
- Add `stage` and `detail` fields to TaskStatusResponse schema
- Pass task instance to helper functions via `task=None` parameter

### Plan 8.1.2: Backend -- Multi-file Upload Endpoint
- New `POST /activities/upload` accepting `List[UploadFile]`
- Handle .zip files with FIT extraction
- Safety limits: 500 files/zip, 50MB/file, depth 5, ratio 10:1
- Keep existing `POST /activities/upload-fit` for backward compat

### Plan 8.1.3: Frontend -- Drag-and-Drop Upload Zone
- Replace UploadButton with UploadZone component
- HTML5 drag-and-drop API with visual feedback
- Support .fit and .zip files, multiple files at once
- Per-file status display (uploading/processing/done/error)

### Plan 8.1.4: Frontend -- Real-Time Processing Status
- ProcessingStatus component with progress bar
- useTaskPolling hook (2s interval polling GET /tasks/{task_id})
- Update TaskStatus type with progress/stage/detail/error fields
- Auto-refresh activity list on completion

## Success Criteria
1. Users can drag-and-drop .fit/.zip files onto the activities page
2. Upload progress bar shows real HTTP upload percentage
3. After upload, processing progress bar shows real backend progress
4. Multiple concurrent uploads each show independent progress
5. Processing completion auto-refreshes the activity list
