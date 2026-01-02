# Single Session Enforcement - Deployment Checklist

## Pre-Deployment

- [ ] Review [SINGLE_SESSION_ENFORCEMENT.md](SINGLE_SESSION_ENFORCEMENT.md) documentation
- [ ] Ensure PostgreSQL database is accessible and running
- [ ] Ensure Redis cache is accessible and running
- [ ] Test suite passes: `python test_single_session_enforcement.py`

## Deployment Steps

### 1. Update Python Dependencies

```bash
cd backend
# No new dependencies needed - uses existing alembic, sqlalchemy, fastapi
pip install -r requirements.txt  # Ensure all dependencies installed
```

### 2. Run Database Migration

```bash
cd backend
alembic upgrade head
```

This creates the `user_sessions` table with all necessary indexes:

- `idx_user_sessions_user_id_active` - For finding active sessions per user
- `idx_user_sessions_device_fingerprint` - For device tracking
- `idx_user_sessions_expires_at` - For cleanup
- Unique constraint on `session_token`

### 3. Verify Migration Success

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d virtual_land_world -c "\d user_sessions"

# Should show all columns and indexes
```

### 4. Restart Backend Service

```bash
# Stop existing backend
docker-compose down backend
# Or: kill the uvicorn process

# Start backend
docker-compose up -d backend
# Or: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verify Deployment

```bash
# Test the feature
python test_single_session_enforcement.py

# Should see all tests passing with output like:
# ✓ PASS: Register User - Status: 201
# ✓ PASS: Login (Device1) - Token: eyJhbGciOi...
# ... (more tests) ...
# ✓ ALL TESTS PASSED - Single session enforcement is working correctly!
```

## Post-Deployment

### Monitor Logs

```bash
# Watch backend logs for session-related messages
docker-compose logs -f backend | grep -i session

# Look for entries like:
# INFO:app.services.session_service:Session created: [uuid] (user_id=[uuid])
# INFO:app.api.v1.endpoints.auth:Terminated [n] existing session(s) for user [username]
```

### Database Maintenance

```bash
# Periodically clean up expired sessions (add to cron job)
# Run this query weekly:
UPDATE user_sessions
SET is_active = FALSE
WHERE expires_at < NOW() AND is_active = TRUE;

# Or use the SessionService method:
# await SessionService.cleanup_expired_sessions(db)
```

### Monitor Session Table Size

```sql
-- Check session table size
SELECT
  relname as table_name,
  pg_size_pretty(pg_total_relation_size(relid)) as size
FROM pg_stat_user_tables
WHERE relname = 'user_sessions';

-- If table grows too large, archive old sessions:
-- DELETE FROM user_sessions WHERE expires_at < NOW() - INTERVAL '30 days' AND is_active = FALSE;
```

## Configuration Changes

### Admin Settings (AdminConfig)

The following setting controls session behavior:

```python
max_sessions_per_user = 1  # Set in admin panel
# 1 = Single session enforcement (this deployment)
# >1 = Multiple sessions allowed (future)
```

This can be configured via the admin panel at:

```
POST /api/v1/admin/config
{
  "max_sessions_per_user": 1
}
```

## Rollback Plan

If issues arise and you need to rollback:

### 1. Stop Backend

```bash
docker-compose down backend
# Or: kill uvicorn process
```

### 2. Rollback Migration

```bash
cd backend
alembic downgrade -1

# This removes the user_sessions table
```

### 3. Restart Backend

```bash
docker-compose up -d backend
```

**Note**: This will lose all session data. Users will need to re-login.

## Breaking Changes

None. This feature is backwards compatible:

- Old JWT tokens continue to work
- Existing API endpoints unchanged
- Only adds new session validation (rejection of multi-session attempts)

## Known Limitations

1. **IP-based Fingerprinting**

   - Users behind proxies/VPNs may be blocked
   - Solution: User can manually logout old session via API

2. **User-Agent Spoofing**

   - User-agent can be forged
   - Not critical - IP address provides additional fingerprinting

3. **Shared Network**
   - Users on same network (office, home WiFi) have same IP
   - Solution: Device fingerprint based on both IP + User-Agent

## Testing in Production

### Test with Real Devices

1. Log in from browser (Chrome, Firefox, Safari)
2. Log in from mobile app (iOS, Android)
3. Verify only last login works
4. Test logout from one device
5. Verify can then log in from another device

### Load Testing

```bash
# Test concurrent login attempts
ab -n 100 -c 10 http://localhost:8000/api/v1/auth/login
```

## Support & Debugging

### Enable Debug Logging

```python
# In app/config.py, add:
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable:
LOGLEVEL=DEBUG
```

### Common Issues & Solutions

**Issue**: "Another device is already using this account"

- **Cause**: Single session enforcement working correctly
- **Solution**: Logout from old device first, or wait for session to expire

**Issue**: All tokens rejected after deployment

- **Cause**: Migration not applied
- **Solution**: Run `alembic upgrade head` again

**Issue**: New sessions not created

- **Cause**: PostgreSQL connection issue
- **Solution**: Check DATABASE_URL, verify PostgreSQL running

**Issue**: Redis errors in logs

- **Cause**: Redis cache not available
- **Solution**: Sessions still work with database, but slower. Verify Redis running.

## Success Metrics

Track these metrics after deployment:

```sql
-- Active sessions count
SELECT COUNT(*) as active_sessions
FROM user_sessions
WHERE is_active = TRUE AND expires_at > NOW();

-- Users with active sessions
SELECT COUNT(DISTINCT user_id) as users_online
FROM user_sessions
WHERE user_id IS NOT NULL AND is_active = TRUE AND expires_at > NOW();

-- Terminated sessions (per day)
SELECT DATE(updated_at) as date, COUNT(*) as terminated_count
FROM user_sessions
WHERE is_active = FALSE
GROUP BY DATE(updated_at)
ORDER BY date DESC;
```

## Contact & Escalation

For issues during or after deployment:

1. Check logs: `docker-compose logs backend`
2. Verify migration: `\d user_sessions` in psql
3. Review [SINGLE_SESSION_ENFORCEMENT.md](SINGLE_SESSION_ENFORCEMENT.md)
4. Check test results: `python test_single_session_enforcement.py`

---

**Deployment Date**: ****\_\_\_****
**Deployed By**: ****\_\_\_****
**Status**: [ ] Success [ ] Rollback [ ] Issues
**Notes**: ********************************\_********************************
