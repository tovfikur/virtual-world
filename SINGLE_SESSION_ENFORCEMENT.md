# Single Session Enforcement - Implementation Guide

## Overview

Implemented a **single-session-per-user policy** for authenticated users while allowing unlimited concurrent sessions for anonymous users. This prevents account takeovers and unauthorized simultaneous access.

## Key Features

### 1. **Single Session Enforcement**

- **Authenticated Users**: Only ONE active session per user at any time
- **Anonymous Users**: Unlimited sessions allowed
- **Automatic Termination**: Previous sessions are automatically terminated when user logs in from a new device

### 2. **Device Fingerprinting**

- Sessions are tracked with device identification using:
  - User-Agent (browser/app identifier)
  - Client IP address
  - Combined SHA256 fingerprint for uniqueness

### 3. **Session Validation**

- Every API request validates that:
  - Session token is active in database
  - Session hasn't expired
  - Session belongs to the authenticated user
  - No conflicting sessions exist

### 4. **Dual Storage**

- **Database (PostgreSQL)**: Persistent session records with device info
- **Cache (Redis)**: Quick access for active session checking

## Database Schema

### UserSession Table

```sql
CREATE TABLE user_sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID FOREIGN KEY (users.user_id),
    session_token VARCHAR(512) UNIQUE NOT NULL,
    device_fingerprint VARCHAR(255) NOT NULL,
    user_agent VARCHAR(512),
    ip_address VARCHAR(45) NOT NULL,
    started_at TIMESTAMP WITH TIMEZONE NOT NULL,
    last_activity TIMESTAMP WITH TIMEZONE NOT NULL,
    expires_at TIMESTAMP WITH TIMEZONE NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIMEZONE NOT NULL,
    updated_at TIMESTAMP WITH TIMEZONE NOT NULL,

    INDEXES:
    - idx_user_sessions_user_id_active (user_id, is_active)
    - idx_user_sessions_device_fingerprint (device_fingerprint)
    - idx_user_sessions_expires_at (expires_at)
    - idx_user_sessions_session_token (session_token) UNIQUE
);
```

## Architecture

### Components

#### 1. **UserSession Model** (`app/models/session.py`)

```python
class UserSession(BaseModel):
    """Tracks active user sessions with device fingerprinting."""
    session_id: UUID
    user_id: Optional[UUID]  # NULL for anonymous
    session_token: str  # JWT session_id claim
    device_fingerprint: str  # SHA256(user-agent:ip)
    user_agent: str
    ip_address: str
    started_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool
```

#### 2. **SessionService** (`app/services/session_service.py`)

Core session management service providing:

- `create_session()` - Create new session with automatic conflict resolution
- `get_session()` - Retrieve session by ID
- `get_session_by_token()` - Retrieve session by token string
- `get_active_sessions()` - Get all active sessions for user
- `validate_session()` - Check if session is valid and active
- `update_activity()` - Update last activity timestamp
- `terminate_session()` - Mark session as inactive
- `terminate_all_sessions()` - Terminate all sessions for user
- `cleanup_expired_sessions()` - Cleanup expired sessions (maintenance)
- `check_duplicate_session()` - Check for duplicate sessions on same device

#### 3. **Updated Auth Endpoints** (`app/api/v1/endpoints/auth.py`)

**Login Endpoint (`POST /api/v1/auth/login`)**:

```python
async def login():
    # 1. Authenticate user (email/password)
    # 2. Check login policy (max_sessions_per_user)
    # 3. TERMINATE existing sessions (single-session enforcement)
    # 4. Create new session in database with device fingerprint
    # 5. Create JWT tokens bound to session
    # 6. Store session in Redis cache
    # 7. Return tokens + previous_session_terminated flag
```

**Logout Endpoint (`POST /api/v1/auth/logout`)**:

```python
async def logout():
    # 1. Validate JWT token
    # 2. Delete refresh token from Redis
    # 3. Delete session from Redis
    # 4. Terminate session in database
    # 5. Return 204 No Content
```

#### 4. **Updated Dependencies** (`app/dependencies.py`)

**get_current_user()**:

```python
async def get_current_user():
    # 1. Verify JWT signature and expiration
    # 2. Validate user exists in database
    # 3. Check account status (not locked, not banned)
    # 4. VALIDATE SESSION IN DATABASE
    # 5. Check session not expired
    # 6. Verify session_id in token matches active session
    # 7. Update last_activity timestamp
    # 8. Return token payload
```

## Security Features

### 1. **Automatic Session Termination**

When user logs in from a new device/browser:

- Previous session is marked as `is_active = FALSE`
- Old JWT tokens become invalid
- Redirect tokens are invalidated
- Old device is forced to re-authenticate

### 2. **Device Fingerprinting**

Tracks sessions by:

- User-Agent string (identifies browser/app type)
- IP address (identifies network location)
- Combined SHA256 hash for uniqueness

### 3. **Dual Validation**

Sessions validated against:

- **Database**: Source of truth for session validity
- **Cache**: Fast-path validation for performance
- Both must agree for access to be granted

### 4. **Activity Tracking**

- `last_activity` timestamp updated on each request
- Can be used for session timeout policies
- Helps identify stale/abandoned sessions

### 5. **Token Binding**

- JWT includes `session_id` claim
- Token tied to specific session
- Tokens from terminated sessions are rejected

## API Response Examples

### Successful Login

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "previous_session_terminated": true,
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "user",
    ...
  }
}

Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Max-Age=604800
```

### Session Terminated Response

```json
{
  "detail": "Session expired or invalid"
}
HTTP 401 Unauthorized
```

### Successful Logout

```
HTTP 204 No Content
Set-Cookie: refresh_token=; HttpOnly; Secure; SameSite=Strict; Max-Age=0
```

## Configuration

### AdminConfig Settings

```python
# In AdminConfig model:
max_sessions_per_user: int = 1  # 1 = single session enforcement
```

### Environment Variables

No additional environment variables needed. Uses existing:

- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis cache connection
- `JWT_SECRET_KEY` - Token signing

## Testing

### Run Test Suite

```bash
# Start backend server
python -m uvicorn app.main:app --reload

# In another terminal, run tests
python test_single_session_enforcement.py
```

### Test Coverage

- ✓ User registration
- ✓ Login from device 1
- ✓ Verify device 1 session active
- ✓ Login from device 2 (terminates device 1)
- ✓ Previous session flag set correctly
- ✓ Device 1 token becomes invalid
- ✓ Device 2 token becomes invalid after device 3 login
- ✓ Logout functionality
- ✓ Logout invalidates token

## Migration

### Database Migration

```bash
# Run migrations
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

**Migration File**: `alembic/versions/f4e8c9b2d5a1_add_user_sessions_table.py`

## Performance Considerations

### Indexes

- `(user_id, is_active)`: Quick lookup of active sessions per user
- `(device_fingerprint)`: Detect duplicate devices
- `(expires_at)`: Cleanup expired sessions
- `(session_token)`: Unique constraint for token lookup

### Caching Strategy

- Session metadata cached in Redis for 24 hours
- Database is source of truth for validation
- Cache used for performance, DB used for security

### Query Optimization

- Sessions fetched by token (indexed) instead of full scans
- Expired sessions marked inactive (not deleted) for audit trail
- Batch termination for multiple sessions

## Troubleshooting

### Issue: "Session expired or invalid" on valid token

**Solution**:

- Check session exists in `user_sessions` table
- Verify `is_active = TRUE`
- Check `expires_at > NOW()`
- Ensure Redis cache is available

### Issue: Multiple sessions active for single user

**Solution**:

- Verify login endpoint calls `SessionService.terminate_all_sessions()`
- Check that old sessions are marked `is_active = FALSE`
- Run cleanup job: `SessionService.cleanup_expired_sessions()`

### Issue: Device fingerprinting too strict

**Solution**:

- Adjust fingerprint method in `SessionService.generate_device_fingerprint()`
- Consider using only IP (not user-agent) for more lenient matching
- Or use more sophisticated fingerprinting (browser plugins, fonts, etc.)

## Future Enhancements

1. **Session Management API**

   - List active sessions
   - Terminate specific session remotely
   - View session details (device, IP, activity)

2. **Configurable Session Limits**

   - Allow admin to set sessions per user
   - Different limits for different user roles

3. **Session Alerts**

   - Notify user of new login from new device
   - Suspicious activity detection

4. **Geolocation Tracking**

   - Track session location
   - Alert user if login from unexpected location

5. **WebRTC Session Binding**
   - Bind WebRTC connections to specific session
   - Prevent cross-device media sharing

## Files Modified/Created

### New Files

- `backend/app/models/session.py` - UserSession ORM model
- `backend/app/services/session_service.py` - Session management service
- `backend/alembic/versions/f4e8c9b2d5a1_add_user_sessions_table.py` - Migration
- `test_single_session_enforcement.py` - Test suite

### Modified Files

- `backend/app/api/v1/endpoints/auth.py` - Updated login/logout endpoints
- `backend/app/dependencies.py` - Enhanced session validation
- `backend/app/models/__init__.py` - Export UserSession model

## Compliance

- ✓ GDPR: Session data tied to users, deletable on request
- ✓ Security Best Practices: JWT binding, device fingerprinting, activity tracking
- ✓ Performance: Efficient queries with proper indexing
- ✓ Auditability: All sessions logged in database with timestamps
