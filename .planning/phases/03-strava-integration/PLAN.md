## Phase 3: Strava Integration

**Goal**: User can connect Strava account and automatically import activities via webhooks
**Requirements**: DATA-02
**Dependencies**: Phase 2

### Plan 3.1: Strava OAuth2 Flow

**Description**: Implement Strava OAuth2 authorization code flow so users can connect their Strava account to the application.

**Files to create**:
- `backend/app/services/strava_service.py` -- Strava OAuth2 client: build auth URL, exchange code for tokens, refresh tokens
- `backend/app/routers/integrations.py` -- extend with GET /integrations/strava/authorize (redirect to Strava), GET /integrations/strava/callback (exchange code), DELETE /integrations/strava/disconnect
- `backend/app/models/integration.py` -- extend with Strava-specific fields (access_token_encrypted, refresh_token_encrypted, token_expires_at, athlete_id)
- `backend/alembic/versions/007_strava_integration.py` -- migration for Strava token fields
- `backend/app/schemas/integration.py` -- extend with StravaAuthUrl, StravaCallbackResponse
- `backend/tests/test_services/test_strava_service.py`

**Technical approach**:
- Use stravalib library for API interactions
- OAuth2 flow:
  1. GET /integrations/strava/authorize: generate Strava auth URL with scopes (read,activity:read_all), redirect user
  2. User authorizes on Strava, redirected to callback URL
  3. GET /integrations/strava/callback?code=XXX: exchange code for access_token + refresh_token
  4. Store tokens encrypted (Fernet) in integration record
  5. Store Strava athlete_id for deduplication
- Token refresh: access tokens expire (6 hours), refresh automatically before API calls
- Scopes needed: `read,activity:read_all` (read public and private activities)
- Store STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in env vars

**Acceptance criteria**:
- User clicks "Connect Strava" -> redirected to Strava authorization page
- After authorizing -> redirected back with tokens stored
- GET /integrations/strava/status shows connected with athlete info
- Token refresh works when access token expired
- Disconnect removes tokens from database

**Estimated complexity**: M

---

### Plan 3.2: Strava Activity Sync

**Description**: Fetch activities from Strava API, download detailed stream data, and import through the existing pipeline.

**Files to create**:
- `backend/app/services/strava_service.py` -- extend with fetch_activities_since(last_sync), fetch_activity_streams(activity_id), fetch_activity_detail(activity_id)
- `backend/app/workers/tasks/strava_sync.py` -- Celery tasks: sync_strava_activities(user_id), fetch_strava_activity(user_id, strava_activity_id)
- `backend/app/services/strava_rate_limiter.py` -- rate limit tracker: 200 requests/15min, 2000/day, exponential backoff on 429
- `backend/tests/test_services/test_strava_sync.py`

**Technical approach**:
- Sync flow:
  1. Fetch activity list from Strava (paginated, since last_sync_at)
  2. For each activity: check if already imported (external_id match)
  3. For new activities: fetch detailed streams (time, watts, heartrate, cadence, velocity_smooth, altitude, latlng, distance)
  4. Convert Strava data format to internal format (same as FIT parser output)
  5. Create activity record with source=strava
  6. Bulk insert stream data into activity_streams hypertable
  7. Trigger metric computation (same pipeline as FIT import)
  8. Update integration.last_sync_at
- Rate limiting:
  - Track requests per 15-min window and per day
  - Before each request: check if limits would be exceeded
  - On 429 response: read Retry-After header, sleep, retry
  - Exponential backoff: 1s, 2s, 4s, 8s, max 60s
- Strava streams may not have power data (not all users have power meters): handle gracefully
- GPS data from Strava is already in degrees (no semicircle conversion needed)
- Manual sync endpoint: POST /integrations/strava/sync triggers full sync

**Acceptance criteria**:
- After connecting Strava: manual sync imports recent activities
- Activities appear with source=strava in activity list
- Stream data stored correctly (power, HR, GPS, etc.)
- Metrics automatically computed after sync
- Duplicate activities not re-imported
- Rate limits respected (no 429 errors in normal operation)
- Activities without power data import successfully (power fields null)

**Estimated complexity**: L

---

### Plan 3.3: Strava Webhook Subscription

**Description**: Set up Strava webhook subscription for real-time activity notifications. When a user uploads a ride to Strava, it automatically appears in our system.

**Files to create**:
- `backend/app/routers/webhooks.py` -- POST /webhooks/strava (event receiver), GET /webhooks/strava (subscription verification)
- `backend/app/services/strava_webhook_service.py` -- webhook validation, event routing
- `backend/app/workers/tasks/strava_sync.py` -- extend with process_strava_webhook(event_data) task
- `backend/tests/test_routers/test_webhooks.py`

**Technical approach**:
- Strava webhook subscription:
  1. Register webhook via Strava API (POST to strava.com/api/v3/push_subscriptions)
  2. Strava sends GET to callback URL with hub.challenge -- must respond with challenge value
  3. On new activity: Strava sends POST with {object_type: "activity", aspect_type: "create", object_id: 12345, owner_id: 67890}
- Webhook handler:
  1. Verify webhook signature (if Strava provides one)
  2. Look up user by Strava athlete_id (owner_id)
  3. Queue Celery task to fetch and import the activity
  4. Return 200 immediately (Strava requires fast response)
- Handle webhook events:
  - `create`: new activity -> fetch and import
  - `update`: activity edited -> re-fetch and update
  - `delete`: activity deleted on Strava -> optionally mark as deleted
- Webhook URL must be publicly accessible (for production: through Nginx/reverse proxy)
- For dev/testing: use ngrok or similar tunnel

**Acceptance criteria**:
- Strava webhook subscription created successfully
- GET /webhooks/strava responds to hub.challenge verification
- New Strava activity -> webhook received -> activity imported within 5 minutes
- Activity update webhook triggers re-import
- Webhook responds within 2 seconds (async processing)
- Invalid webhook payloads rejected

**Estimated complexity**: M

---

### Plan 3.4: Historical Strava Backfill

**Description**: Import all historical activities from Strava for users who connect their account. Handles large histories with rate limit awareness.

**Files to create**:
- `backend/app/services/strava_service.py` -- extend with backfill_all_activities(user_id)
- `backend/app/workers/tasks/strava_sync.py` -- extend with strava_historical_backfill(user_id) task
- `backend/app/routers/integrations.py` -- extend with POST /integrations/strava/backfill

**Technical approach**:
- Backfill fetches ALL activities from Strava (paginated, 200 per page, sorted by date)
- Rate limit aware: with 200 req/15min limit and needing 2 requests per activity (list + streams), can process ~100 activities per 15-min window
- For 1500 activities: approximately 30 minutes total (queued over multiple rate limit windows)
- Progress tracking: store backfill status in integration record (total_activities, imported, remaining)
- Deduplication: check external_id before importing each activity
- Queue on low_priority to avoid blocking real-time imports
- User can check progress via GET /integrations/strava/status

**Acceptance criteria**:
- Backfill imports all historical Strava activities
- Rate limits respected throughout (no 429 errors)
- Progress visible via status endpoint
- Pre-existing activities (from FIT upload) not duplicated
- Backfill can be interrupted and resumed (tracks last processed page)
- Completes for 1500 activities within ~45 minutes

**Estimated complexity**: M

---

### Phase 3 Verification

```bash
# 1. Strava OAuth flow
curl http://localhost:8000/integrations/strava/authorize
# Expected: redirect URL to Strava authorization page

# 2. After authorization callback
curl http://localhost:8000/integrations/strava/status
# Expected: {"connected": true, "athlete_id": 12345, "last_sync": null}

# 3. Manual sync
curl -X POST http://localhost:8000/integrations/strava/sync
# Expected: {"task_id": "...", "status": "queued"}

# 4. Webhook verification
curl "http://localhost:8000/webhooks/strava?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=STRAVA_VERIFY_TOKEN"
# Expected: {"hub.challenge": "test123"}

# 5. Activities imported from Strava
curl http://localhost:8000/activities?source=strava
# Expected: list of Strava-imported activities with metrics

# 6. Run tests
cd backend && uv run pytest tests/test_services/test_strava*.py -v
```

