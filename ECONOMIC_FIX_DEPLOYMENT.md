# Economic Settings Fix - Deployment & Testing Guide

## What Was Fixed

**Problem:** Admin economic settings (biome prices, elevation factors) were not reflected in the UI when buying/selling land.

**Root Cause:** Land prices were stored in the database when created, but were never recalculated when admin changed the config.

**Solution:** Implemented dynamic price recalculation that fetches current admin config every time land data is returned.

## Changes Made

### Backend Files Modified
1. **`backend/app/api/v1/endpoints/lands.py`**
   - Added `_calculate_current_land_price()` function
   - Updated `_serialize_land()` to recalculate prices

2. **`backend/app/api/v1/endpoints/chunks.py`**
   - Added `_calculate_unclaimed_land_price()` function  
   - Updated `enrich_chunk_with_ownership()` to recalculate prices

### No Changes Required
- ✅ Frontend works as-is (no code changes needed)
- ✅ Database schema unchanged
- ✅ API contracts unchanged
- ✅ Response format identical

## Deployment Steps

### 1. Pull Latest Code
```bash
git pull origin main
cd backend
```

### 2. Install Dependencies (if needed)
```bash
pip install -r requirements.txt
```

### 3. Restart Backend Service
```bash
# Stop current service
docker-compose down

# Rebuild and restart
docker-compose up -d

# Or if using systemd/direct Python
systemctl restart virtualworld-backend
# OR
python -m uvicorn app.main:app --reload
```

### 4. Verify Deployment
```bash
curl http://localhost:8000/api/v1/health
# Should return 200 OK
```

## Testing Checklist

### Test 1: Basic Price Display
1. Open World page and select a land
2. Check LandInfoPanel shows correct price
3. **Expected:** Price should match formula: `base_price * elevation_factor`

### Test 2: Admin Update Reflects Immediately
1. Go to Admin Dashboard → Economy Settings
2. Change "Plains Base Price" from 125 to 150
3. Click Save
4. Go back to World page, select a plains land
5. **Expected:** Price should increase to ~150 BDT

### Test 3: Multi-Select Pricing
1. Select multiple unowned lands of different biomes
2. Check total price in MultiLandActionsPanel
3. **Expected:** Total should be sum of all individual prices

### Test 4: Elevation Factor Works
1. Admin: Set elevation factors to min=1.0, max=1.0 (flat pricing)
2. Select lands at different elevations
3. **Expected:** All should show same price regardless of elevation

### Test 5: Batch Chunk Loading
1. Zoom out to view multiple chunks
2. Check chunk load endpoint returns correct prices
3. **Expected:** Prices should match admin config

### Test 6: Purchase at Current Price
1. Admin: Set plains price to 500 BDT
2. Select an unowned plains land
3. Attempt to purchase
4. **Expected:** Should charge at current price (500 BDT), not old price

## Monitoring

### Check Logs for Errors
```bash
docker logs virtualworld-backend
# Look for: "Failed to recalculate"
```

### Performance Metrics
- Price recalculation adds minimal overhead (single DB query for AdminConfig)
- AdminConfig is cached per request (not globally cached, intentional)
- Fallback to stored price if calculation fails

## Rollback (if needed)
```bash
git revert <commit-hash>
docker-compose down
docker-compose up -d
```

## Configuration

No new environment variables needed. The system uses existing:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Cache (optional)

## FAQ

**Q: Will this affect performance?**
A: Minimal impact. Each land response triggers one admin config fetch. Can be optimized with caching if needed.

**Q: Do I need to migrate the database?**
A: No. No schema changes required.

**Q: What if admin config is missing?**
A: Falls back to stored price_base_bdt from the database.

**Q: Do existing land purchase prices change?**
A: Only the displayed price changes. Purchase logic uses the current price at time of purchase (correct behavior).

**Q: Can I cache admin config?**
A: Yes, modify `_calculate_current_land_price()` and `_calculate_unclaimed_land_price()` to cache with TTL if needed.

## Files to Review
- [Economic Settings Fix Documentation](./ECONOMIC_SETTINGS_FIX.md)
- `backend/app/api/v1/endpoints/lands.py` (lines 48-132)
- `backend/app/api/v1/endpoints/chunks.py` (lines 24-90, 183)

## Support
If prices still don't update:
1. Check admin config was saved: `GET /admin/config/economy`
2. Verify database connection: Check PostgreSQL logs
3. Check for errors: `docker logs virtualworld-backend | grep -i price`
4. Clear browser cache: Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
