# Trading System - Step-by-Step Testing Instructions

## 🎯 Quick Test (5 minutes)

### Prerequisites

- Running backend server (localhost:8000)
- Admin account with valid token
- User account with valid token
- Owned land or ability to claim land

### Test Steps

#### Step 1: Verify API Returns Field (1 minute)

Open terminal or Postman:

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response** (abbreviated):

```json
{
  "base_land_price_bdt": 1000,
  "transaction_fee_percent": 5,
  "enable_land_trading": true,    ← ✅ See this field!
  "biome_market_controls": {...}
}
```

**✅ Pass Criteria**: Response includes `"enable_land_trading": true` or `false`  
**❌ Fail Criteria**: Field is missing or `undefined`

---

#### Step 2: Verify Admin UI Shows Checkbox (1 minute)

1. Open browser: `http://localhost:3000` (or your frontend URL)
2. Login as admin
3. Navigate to: **Admin** → **Economic Settings**
4. Scroll to "**General Land Pricing**" section
5. Look for checkbox labeled "**Enable Land Trading**"

**✅ Pass Criteria**:

- Checkbox is visible
- It's either checked or unchecked (showing a state)
- Not blank or greyed out

**❌ Fail Criteria**:

- Checkbox is missing
- Checkbox is always unchecked regardless of setting
- Checkbox doesn't respond to clicks

---

#### Step 3: Toggle Trading OFF (2 minutes)

**In Admin UI:**

1. Make sure "Enable Land Trading" checkbox is **UNCHECKED**
2. Click **SAVE** button
3. Wait for "Success" message

**Verify via API:**

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**✅ Pass Criteria**: Response has `"enable_land_trading": false`

**In Frontend:**

1. Reload the admin page (F5)
2. Checkbox should still be **UNCHECKED**

**✅ Pass Criteria**: Checkbox is checked/unchecked persistently

---

#### Step 4: Try to Trade When Disabled (1 minute)

As a **regular user**, try to create a listing:

```bash
curl -X POST http://localhost:8000/marketplace/listings \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "land_ids": ["existing-land-uuid"],
    "listing_type": "fixed_price",
    "buy_now_price_bdt": 150000
  }'
```

**✅ Pass Criteria**:

- Response status: **403 Forbidden**
- Response body: `{"detail": "Land trading is currently disabled by admin"}`

**❌ Fail Criteria**:

- Status 201 Created (listing was created - BAD!)
- Status 200 OK (operation succeeded - BAD!)
- Any status other than 403

---

#### Step 5: Enable Trading and Verify (1 minute)

**In Admin UI:**

1. **CHECK** the "Enable Land Trading" checkbox
2. Click **SAVE**
3. Wait for success message

**In Terminal:**

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**✅ Pass Criteria**: Response has `"enable_land_trading": true`

**In Frontend:**

1. Reload (F5)
2. Checkbox should be **CHECKED**

---

#### Step 6: Try to Trade When Enabled (1 minute)

As a **regular user**, create a listing again:

```bash
curl -X POST http://localhost:8000/marketplace/listings \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "land_ids": ["existing-land-uuid"],
    "listing_type": "fixed_price",
    "buy_now_price_bdt": 150000
  }'
```

**✅ Pass Criteria**:

- Status: **201 Created** (or 400 if land IDs invalid, but NOT 403)
- Response body has: `"listing_id": "..."`

**❌ Fail Criteria**:

- Status 403 Forbidden (should work now!)
- Status 500 Internal Server Error

---

## 🧪 Complete Test Suite (15 minutes)

If quick test passes, run the full suite:

### Test 1: API Serialization

**Objective**: Verify all fields are in API response

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" | jq .enable_land_trading
```

**Expected**: `true` or `false` (not `null`)

---

### Test 2: Toggle ON → OFF → ON

**Step 1: Set to ON**

```bash
curl -X PATCH http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enable_land_trading": true}'
```

**Verify**: Response shows `"enable_land_trading": true`

**Step 2: Get and verify persistence**

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" | jq .enable_land_trading
```

**Expected**: `true`

**Step 3: Set to OFF**

```bash
curl -X PATCH http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enable_land_trading": false}'
```

**Verify**: Response shows `"enable_land_trading": false`

**Step 4: Get and verify**

```bash
curl -X GET http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" | jq .enable_land_trading
```

**Expected**: `false`

**Step 5: Set to ON again**

```bash
curl -X PATCH http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enable_land_trading": true}'
```

**Verify**: Response shows `"enable_land_trading": true`

---

### Test 3: Transaction Blocking

#### When Trading is OFF

**Disable trading first:**

```bash
curl -X PATCH http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"enable_land_trading": false}'
```

**Try each endpoint:**

**3a. Create Listing**

```bash
curl -X POST http://localhost:8000/marketplace/listings \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -d '{"land_ids": ["..."], "listing_type": "fixed_price", ...}'
```

**Expected**: 403 Forbidden ✅

**3b. Place Bid**

```bash
curl -X POST http://localhost:8000/marketplace/listings/LISTING_ID/bids \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -d '{"amount_bdt": 150000}'
```

**Expected**: 403 Forbidden ✅

**3c. Buy Now**

```bash
curl -X POST http://localhost:8000/marketplace/listings/LISTING_ID/buy-now \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -d '{"payment_method": "balance"}'
```

**Expected**: 403 Forbidden ✅

**3d. Claim Land**

```bash
curl -X POST http://localhost:8000/lands/claim \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -d '{"x": 100, "y": 100, "biome": "plains"}'
```

**Expected**: 403 Forbidden ✅

---

#### When Trading is ON

**Enable trading first:**

```bash
curl -X PATCH http://localhost:8000/admin/config/economy \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"enable_land_trading": true}'
```

**Try same endpoints - should work (or give different error):**

**3a. Create Listing**

- Expected: 201 Created ✅ (or 400 if bad data, but NOT 403)

**3b. Place Bid**

- Expected: 201 Created ✅ (or 400/404, but NOT 403)

**3c. Buy Now**

- Expected: 200 OK ✅ (or 400/404, but NOT 403)

**3d. Claim Land**

- Expected: 200 OK ✅ (or 400, but NOT 403)

---

### Test 4: Frontend Persistence

**Objective**: UI correctly reflects and persists settings

**Step 1: Open Admin Settings**

- Go to Admin → Economic Settings
- Note current state of "Enable Land Trading" checkbox

**Step 2: Reload Page**

- Press F5 (refresh)
- Checkbox should be in same state

**Step 3: Toggle Checkbox**

- Click checkbox to opposite state
- Click SAVE
- See "Success" message

**Step 4: Reload Again**

- Press F5
- Checkbox should be in NEW state

**✅ Pass**: Checkbox state is persistent across page reloads

---

### Test 5: Rate Limiting Not Affected

Trading enforcement shouldn't affect rate limiting:

```bash
# Make 5 requests rapidly (all trading OFF)
for i in {1..5}; do
  curl -X GET http://localhost:8000/admin/config/economy \
    -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
done
```

**Expected**: All succeed (rate limiting still works normally)

---

## 📋 Test Results Template

Use this to document results:

```
TEST ENVIRONMENT:
- Backend: localhost:8000 ✓
- Frontend: localhost:3000 ✓
- Database: PostgreSQL ✓
- Redis: Running ✓

TEST DATE: ___________
TESTER: ___________

QUICK TESTS (Required):
┌─ Test 1: API Returns Field ✓ / ✗ / N/A
│
├─ Test 2: Admin UI Shows Checkbox ✓ / ✗ / N/A
│
├─ Test 3: Toggle Trading OFF ✓ / ✗ / N/A
│
├─ Test 4: Try Trade When OFF → 403 ✓ / ✗ / N/A
│
├─ Test 5: Toggle Trading ON ✓ / ✗ / N/A
│
└─ Test 6: Try Trade When ON → Success ✓ / ✗ / N/A

FULL TESTS (Optional):
├─ Test 1: API Serialization ✓ / ✗ / N/A
│
├─ Test 2: Toggle ON→OFF→ON ✓ / ✗ / N/A
│
├─ Test 3: Transaction Blocking ✓ / ✗ / N/A
│  ├─ Create Listing Blocked ✓ / ✗
│  ├─ Place Bid Blocked ✓ / ✗
│  ├─ Buy Now Blocked ✓ / ✗
│  └─ Claim Land Blocked ✓ / ✗
│
├─ Test 4: Frontend Persistence ✓ / ✗ / N/A
│
└─ Test 5: Rate Limiting ✓ / ✗ / N/A

OVERALL RESULT: ✓ PASS / ✗ FAIL

NOTES:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

---

## 🐛 If Tests Fail

### Issue: API Still Doesn't Return Field

**Check:**

1. Code is deployed: `git log` shows commit e857f7a
2. Server restarted/reloaded
3. Using correct endpoint: `/admin/config/economy`
4. Admin token is valid

**Fix:** Restart backend server, clear frontend cache

---

### Issue: Checkbox Still Unchecked

**Check:**

1. API is returning the field (do Test 1 first)
2. Browser cache is cleared (Ctrl+Shift+Del)
3. Frontend reloaded (Ctrl+Shift+R hard refresh)

**Fix:** Clear browser storage and reload

---

### Issue: Trading Still Works When Disabled

**Check:**

1. Admin actually saved (see success message)
2. Verify via API it's set to false
3. User is using fresh token (not cached)
4. Server restarted after code deployment

**Fix:** Check logs for enforcement errors:

```bash
grep "enable_land_trading" /var/log/backend.log
```

---

### Issue: Trading Blocked When Enabled

**Check:**

1. API shows `"enable_land_trading": true`
2. Using correct endpoint
3. User has valid lands to list
4. No other errors (check response body)

**Fix:** Check full error response:

```bash
curl ... -v  # Verbose mode shows headers and full response
```

---

## ✅ Sign-Off Checklist

Before deploying to production:

- [ ] Quick Test (6 tests) - All PASS
- [ ] Full Test Suite (5 tests) - All PASS
- [ ] Frontend UI works correctly
- [ ] API responses correct
- [ ] Database persistence verified
- [ ] No server errors in logs
- [ ] Rate limiting unaffected
- [ ] Backward compatible (existing data OK)
- [ ] Documented and approved
- [ ] Ready for production deployment

---

## Questions?

Refer to:

- [Root Cause Analysis](./TRADING_SYSTEM_ROOT_CAUSE_FIX.md)
- [Visual Diagrams](./TRADING_SYSTEM_VISUAL_GUIDE.md)
- [Complete Summary](./TRADING_SYSTEM_FINAL_SUMMARY.md)
