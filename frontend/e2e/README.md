# E2E Tests

End-to-end tests using Playwright.

## Prerequisites

**All services must be running before executing tests:**

1. Backend API server: `http://localhost:8000`
2. Frontend dev server: `http://localhost:5173`
3. TimescaleDB (via Podman)
4. Redis (via Podman)
5. Celery worker (for processing uploads)

Start all services:
```bash
# Terminal 1 - Database and Redis
cd /c/Users/biker/projects/cycling-analytics
podman compose -f docker-compose.dev.yml up -d

# Terminal 2 - Backend
cd /c/Users/biker/projects/cycling-analytics/backend
uv run uvicorn app.main:app --reload

# Terminal 3 - Celery worker
cd /c/Users/biker/projects/cycling-analytics/backend
uv run celery -A app.celery_app worker --loglevel=info --pool=solo

# Terminal 4 - Frontend
cd /c/Users/biker/projects/cycling-analytics/frontend
npm run dev
```

## Running Tests

```bash
# Headless mode (default)
npm run test:e2e

# Headed mode (see browser)
npm run test:e2e:headed

# UI mode (interactive)
npm run test:e2e:ui
```

## Test Credentials

Tests read credentials from `.env.test` at the project root:
- `LOCAL_USER` - Email address
- `LOCAL_PASSWORD` - Password

**Never hardcode credentials in test files.**

## Test Coverage

### upload-and-calendar.spec.ts

Tests the full upload and calendar workflow:

1. Login with credentials from `.env.test`
2. Upload 4 .zip files from `.fitfiles/` directory
3. Wait for Celery processing to complete
4. Verify activities appear in the activity list
5. Navigate to calendar page
6. Test infinite scroll in both directions (older and newer months)
7. Test "Today" button navigation
8. Verify rides appear on correct calendar dates

Expected duration: ~2 minutes (includes Celery processing time)

## Test Files

The test uploads these .zip files:
- `21796666064.zip` (1 .fit file)
- `21817961064.zip` (1 .fit + 1 nested .zip that will be rejected)
- `21817965502.zip` (1 .fit file)
- `21829011561.zip` (1 .fit file)

Total: 4 valid .fit files, 1 nested .zip rejection

## Troubleshooting

**Test timeout during upload:**
- Check Celery worker is running
- Check backend logs for errors
- Increase timeout in `playwright.config.ts` if needed

**Login fails:**
- Verify `.env.test` exists at project root
- Verify credentials match a valid user account
- Check backend is running and accessible

**Activities not appearing:**
- Check Celery worker processed tasks successfully
- Check backend logs for import errors
- Verify TimescaleDB is running and migrations are up-to-date

**Calendar scroll not working:**
- Verify calendar infinite scroll fixes from Plan 8.5.3 are implemented
- Check browser console for JavaScript errors
