# Phase 8.2: Integration Settings & Backfill UI

**Goal**: Users can connect/disconnect Garmin and Strava accounts from Settings, configure backfill time periods, and trigger syncs. Strava OAuth works correctly in browser.

**Requirements**: Garmin & Strava connection UI (#1), Strava OAuth redirect fix

**Dependencies**: Phase 8

## Plans

### Plan 8.2.1: Backend -- Configurable Backfill + Strava OAuth Redirect Fix
- Add `days` query parameter to sync/backfill endpoints (1-3650)
- Add `POST /integrations/garmin/backfill` endpoint
- Fix Strava OAuth callback: RedirectResponse to frontend URL
- Add FRONTEND_URL config setting

### Plan 8.2.2: Frontend -- Integrations Section on Settings Page
- GarminConnect component (email/password form, status, sync, disconnect)
- StravaConnect component (OAuth button, redirect handling, status)
- Read URL query params for strava_connected/strava_error on mount
- API functions for all integration operations

### Plan 8.2.3: Frontend -- Backfill Configuration UI
- BackfillSelector reusable component
- Time periods: 30d, 90d, 6mo, 1yr, 2yr, all time
- Reuse useTaskPolling for backfill progress display

## Success Criteria
1. Settings page shows Garmin connection form (email/password)
2. Settings page shows Strava OAuth "Connect" button
3. Strava OAuth flow redirects back to Settings with success/error state
4. Connected integrations show status, last sync, sync/disconnect controls
5. Users can configure backfill time period and see progress
