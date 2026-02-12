## Phase 5: Multi-User Infrastructure

**Goal**: Multiple users can securely access their own data with authentication
**Requirements**: INFR-01
**Dependencies**: Phase 1

### Plan 5.1: User Authentication with JWT

**Description**: Implement user registration, login, and JWT-based authentication with secure password hashing.

**Files to create**:
- `backend/app/routers/auth.py` -- POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout
- `backend/app/security.py` -- JWT encode/decode, password hashing (bcrypt), token verification dependency
- `backend/app/schemas/auth.py` -- RegisterRequest, LoginRequest, TokenResponse, UserResponse
- `backend/app/dependencies.py` -- extend with get_current_user dependency (JWT verification)
- `backend/tests/test_routers/test_auth.py`

**Technical approach**:
- Password hashing: passlib with bcrypt (or Argon2id via pwdlib for modern best practice)
- JWT tokens: PyJWT with HS256 signing, SECRET_KEY from env
- Token structure: {sub: user_id, exp: timestamp, iat: timestamp, type: "access"|"refresh"}
- Access token: 30-minute expiry
- Refresh token: 7-day expiry, stored in httpOnly cookie
- Login returns access_token in response body + refresh_token in httpOnly cookie
- Protected endpoints use `Depends(get_current_user)` -- extracts and validates JWT from Authorization: Bearer header
- Registration: email + password + display_name, email must be unique
- First user registration could be admin (or all users equal for self-hosted)

**Acceptance criteria**:
- POST /auth/register creates user, returns tokens
- POST /auth/login with valid credentials returns tokens
- POST /auth/login with invalid credentials returns 401
- Protected endpoint without token returns 401
- Protected endpoint with valid token returns data
- Expired token returns 401
- Refresh token generates new access token
- Passwords stored as bcrypt hashes (not plaintext)

**Estimated complexity**: M

---

### Plan 5.2: Data Isolation and Row-Level Security

**Description**: Ensure each user can only access their own data. Add user_id filtering to all queries and protect all API endpoints.

**Files to create**:
- `backend/app/dependencies.py` -- extend with user-scoped DB session or query filters
- `backend/app/services/*.py` -- update all service functions to accept user_id and filter queries
- `backend/app/routers/*.py` -- update all routers to inject current_user and pass user_id to services
- `backend/alembic/versions/009_rls_indexes.py` -- add indexes on user_id columns for performance
- `backend/tests/test_security/test_data_isolation.py` -- multi-user isolation tests

**Technical approach**:
- Application-level data isolation (not PostgreSQL RLS, to keep control):
  - All queries include `WHERE user_id = :current_user_id`
  - Service functions require user_id parameter
  - Router functions get user_id from `Depends(get_current_user)`
- Add composite indexes for performance:
  - `activities(user_id, activity_date DESC)`
  - `daily_fitness(user_id, date, threshold_method)`
  - `activity_metrics(activity_id)` (activity already scoped to user)
  - `thresholds(user_id, method, effective_date DESC)`
  - `health_metrics(user_id, date, metric_type)`
- Test isolation: create 2 users, add data for each, verify user A cannot access user B's data
- All existing endpoints updated with auth dependency

**Acceptance criteria**:
- User A cannot see User B's activities (GET /activities returns only own data)
- User A cannot access User B's metrics (GET /metrics/fitness scoped to current user)
- User A cannot access User B's activity streams (GET /activities/{b_id}/streams returns 403 or 404)
- All API endpoints require authentication (return 401 without token)
- Query performance not degraded (EXPLAIN shows index usage on user_id)
- Integration tests with 2+ users pass

**Estimated complexity**: L

---

### Plan 5.3: User Profile and Setup Wizard

**Description**: Build user profile management and first-run setup wizard for initial configuration.

**Files to create**:
- `backend/app/routers/users.py` -- GET /users/me (profile), PUT /users/me (update profile)
- `backend/app/schemas/user.py` -- UserProfile, UserProfileUpdate
- `backend/app/routers/setup.py` -- GET /setup/status (is setup complete?), POST /setup/init (first-time setup)
- `backend/app/schemas/setup.py` -- SetupStatus, InitialSetupRequest
- `backend/tests/test_routers/test_users.py`

**Technical approach**:
- User profile stores: display_name, email, weight_kg, date_of_birth, preferred_units (metric/imperial), timezone
- First-run setup wizard (API support for frontend in Phase 6):
  1. GET /setup/status: returns {setup_complete: false} if no users exist
  2. POST /setup/init: creates first user (admin), no auth required (only works when 0 users)
  3. Optionally accept Garmin credentials, FTP setting in same request
- After first user created, /setup/init returns 403
- Profile update requires authentication

**Acceptance criteria**:
- First request to /setup/status returns {setup_complete: false}
- POST /setup/init creates first user without requiring auth
- Second POST /setup/init returns 403
- GET /users/me returns profile data
- PUT /users/me updates profile fields
- Profile changes reflected in subsequent API calls

**Estimated complexity**: S

---

### Phase 5 Verification

```bash
# 1. Register and login
curl -X POST http://localhost:8000/auth/register -d '{"email":"rider@test.com","password":"secure123","display_name":"Test Rider"}'
# Expected: 201 with access_token

# 2. Access protected endpoint
TOKEN="<access_token from above>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/activities
# Expected: 200 with activities list

# 3. Access without token
curl http://localhost:8000/activities
# Expected: 401 Unauthorized

# 4. Data isolation (create second user)
curl -X POST http://localhost:8000/auth/register -d '{"email":"rider2@test.com","password":"secure456","display_name":"Other Rider"}'
TOKEN2="<access_token for rider2>"
curl -H "Authorization: Bearer $TOKEN2" http://localhost:8000/activities
# Expected: empty list (rider2 has no activities)

# 5. First-run setup
# (Reset database for this test)
curl http://localhost:8000/setup/status
# Expected: {"setup_complete": false}
curl -X POST http://localhost:8000/setup/init -d '{"email":"admin@test.com","password":"admin123","display_name":"Admin"}'
# Expected: 201

# 6. Run tests
cd backend && uv run pytest tests/test_routers/test_auth.py -v
cd backend && uv run pytest tests/test_security/test_data_isolation.py -v
```

