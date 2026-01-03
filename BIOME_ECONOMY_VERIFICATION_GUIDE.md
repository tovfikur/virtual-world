# Global Biome Economy System - Verification Guide

## Overview

This guide provides step-by-step instructions to verify the Global Biome Economy System is working correctly.

## Pre-Verification Checklist

- [ ] Application started successfully (no errors in logs)
- [ ] Database migrations applied
- [ ] BiomeLandMarket table exists with 7 records (one per biome)
- [ ] No error messages about BiomeLandEconomyService initialization

## Step 1: Verify Database Initialization

### Check BiomeLandMarket Table Exists

```sql
SELECT * FROM biome_land_market;
```

**Expected Result:**
```
biome          | sold_lands_count | average_price_bdt | total_market_value_bdt | last_transaction_at
---------------|------------------|-------------------|------------------------|--------------------
beach          | 0                | 0.0               | 0                      | 2024-01-03 ...
desert         | 0                | 0.0               | 0                      | 2024-01-03 ...
forest         | 0                | 0.0               | 0                      | 2024-01-03 ...
mountain       | 0                | 0.0               | 0                      | 2024-01-03 ...
ocean          | 0                | 0.0               | 0                      | 2024-01-03 ...
plains         | 0                | 0.0               | 0                      | 2024-01-03 ...
snow           | 0                | 0.0               | 0                      | 2024-01-03 ...
```

**✅ Pass**: 7 biomes initialized
**❌ Fail**: Missing biomes or table doesn't exist

## Step 2: Verify Application Logs

### Check Startup Logs

```bash
# Look for these messages in application logs:
"Biome markets initialized"
"Biome land economy markets initialized"
"Application startup complete"
```

**✅ Pass**: Both initialization messages appear
**❌ Fail**: Missing "Biome land economy markets initialized" message

## Step 3: Test Buy Transaction

### Create a Test Purchase

1. Get a buyer user ID with sufficient balance (>10,000 BDT)
2. Create a land listing with some lands
3. Execute purchase for 10,000 BDT

### SQL Query: Check Land Prices Before Purchase

```sql
-- Get average price per biome before purchase
SELECT 
    l.biome,
    AVG(l.price_base_bdt) as avg_price,
    COUNT(*) as land_count
FROM land l
WHERE l.owner_id IS NOT NULL
GROUP BY l.biome;
```

**Record the prices for comparison.**

### Execute Purchase Via API

```bash
POST /api/v1/marketplace/listings/{listing_id}/buy-now
{
    "buyer_id": "your-buyer-uuid"
}
```

### Check Application Logs After Purchase

```
DEBUG: Biome economy updated: {
    "success": True,
    "amount_paid_bdt": 10000,
    "per_biome_share": 1428.57,
    "price_changes": {
        "plains": {"old_price": 1000, "increase": 28.57, ...},
        ...
    }
}

INFO: Land purchase processed: land-uuid, Amount: 10000 BDT, ...
INFO: Buy now completed: listing uuid, ...
```

**✅ Pass**: Debug and info messages show price changes
**❌ Fail**: No economy debug message, or error messages

### SQL Query: Check Land Prices After Purchase

```sql
-- Get average price per biome after purchase
SELECT 
    l.biome,
    AVG(l.price_base_bdt) as avg_price,
    COUNT(*) as land_count
FROM land l
WHERE l.owner_id IS NOT NULL
GROUP BY l.biome;
```

**Expected Result:**
- All biomes with owned lands show higher average prices
- Price increase follows formula: 10,000 ÷ 7 ÷ land_count

### Verify BiomeLandMarket Updated

```sql
SELECT * FROM biome_land_market 
ORDER BY biome;
```

**Expected Result:**
- `last_transaction_at` updated to current timestamp
- `total_market_value_bdt` increased by 10,000 ÷ 7 = ~1,428.57
- `average_price_bdt` recalculated (if lands in biome)

## Step 4: Verify Formula Correctness

### Manual Calculation

**Purchase amount: 10,000 BDT**
**Per-biome share: 10,000 ÷ 7 = 1,428.57 BDT**

For each biome, verify:

```
Price increase = 1,428.57 ÷ number_of_owned_lands_in_biome
```

**Example:**
```
Plains: 1,428.57 ÷ 50 = 28.57 BDT per land
Beach: 1,428.57 ÷ 30 = 47.62 BDT per land
```

### SQL Verification

```sql
-- Get actual price increases per biome
SELECT 
    l.biome,
    COUNT(*) as owned_lands,
    AVG(l.price_base_bdt) - {old_average_price} as avg_increase,
    1428.57 / COUNT(*) as expected_increase
FROM land l
WHERE l.owner_id IS NOT NULL
GROUP BY l.biome;
```

**Expected Result:**
`avg_increase` ≈ `expected_increase` (allow ±0.01 margin)

**✅ Pass**: Prices match formula
**❌ Fail**: Prices don't match formula

## Step 5: Test Zero-Lands Biome

### Check Biome with Zero Owned Lands

```sql
-- Find a biome with no owned lands
SELECT 
    l.biome,
    COUNT(*) as owned_lands
FROM land l
WHERE l.owner_id IS NOT NULL
GROUP BY l.biome;
```

**Identify a biome with 0 owned lands (e.g., Ocean)**

### Make Purchase and Verify

1. Execute purchase for 10,000 BDT
2. Check application logs
3. SQL query: Verify Ocean (0 lands) didn't get updated

**Expected Log:**
```
DEBUG: Biome economy updated: {
    "price_changes": {
        "plains": {...},
        "beach": {...},
        // Notice: "ocean" is MISSING because it has 0 lands
    }
}
```

**✅ Pass**: Zero-lands biome skipped (expected)
**❌ Fail**: Error about division by zero, or unexpected biome update

## Step 6: Test Auction Finalization

### Create and Finalize Auction

1. Create auction listing (not fixed price)
2. Wait for auction to end OR set past end time
3. Manually trigger finalization (or wait for cron job)

### Check Logs

```
DEBUG: Biome economy updated: {...}
INFO: Auction finalized: listing uuid, amount X BDT
```

**✅ Pass**: Same economy update as buy_now
**❌ Fail**: Missing economy update message

### Verify Prices Updated

```sql
SELECT * FROM biome_land_market;
```

**Expected Result:**
- `last_transaction_at` updated after auction finalization
- Market value increased

## Step 7: Test Negative Price Prevention

### Create Multiple Sales (If Enabled)

1. Execute several sales to drive prices down
2. Monitor for prices reaching 0 (should stop there)

**SQL Check:**

```sql
SELECT 
    l.biome,
    MIN(l.price_base_bdt) as min_price,
    MAX(l.price_base_bdt) as max_price,
    AVG(l.price_base_bdt) as avg_price
FROM land l
WHERE l.owner_id IS NOT NULL
GROUP BY l.biome;
```

**Expected Result:**
`min_price` ≥ 0 (never negative)

**✅ Pass**: All prices ≥ 0
**❌ Fail**: Negative prices exist

## Step 8: Test Error Handling

### Simulate Database Error

1. Stop database connection (or simulate database error)
2. Try to execute purchase
3. Verify transaction still completes despite economy service error

**Expected Behavior:**
```
ERROR: Error processing land purchase: Connection timeout
// But transaction still completes successfully
```

**✅ Pass**: Transaction succeeds, economy error logged but non-blocking
**❌ Fail**: Transaction fails due to economy error

## Step 9: Performance Test

### Measure Transaction Time

```bash
# Buy with economy update
POST /api/v1/marketplace/listings/{id}/buy-now

# Measure response time
# Expected: 100-500ms (depending on database performance)
```

**✅ Pass**: < 1 second response time
**⚠️ Warning**: 1-3 seconds (acceptable but slow)
**❌ Fail**: > 3 seconds (investigate database performance)

## Comprehensive Verification Checklist

### Database State
- [ ] BiomeLandMarket table exists with 7 records
- [ ] `last_transaction_at` updates after transactions
- [ ] Land prices update correctly
- [ ] No negative prices

### Application Behavior
- [ ] Startup logs show "Biome land economy markets initialized"
- [ ] Buy transactions trigger economy update
- [ ] Auction finalization triggers economy update
- [ ] Debug logs show formula calculations
- [ ] Error logs show graceful handling of failures

### Formula Accuracy
- [ ] Price increases match C / (X × Xi) formula
- [ ] Zero-lands biomes skipped
- [ ] All owned lands in biome get same increase
- [ ] Per-biome shares calculated correctly

### Error Handling
- [ ] Economy service errors don't block transactions
- [ ] Negative prices prevented
- [ ] Division by zero prevented
- [ ] Concurrent transactions handled safely

## Common Issues & Diagnostics

### Issue: BiomeLandMarket table doesn't exist

**Diagnosis:**
```bash
# Check migrations ran
psql your_db -c "\dt" | grep biome_land_market
```

**Solution:**
```bash
# Run migrations
alembic upgrade head
```

### Issue: Prices not updating after purchase

**Diagnosis:**
1. Check application logs for errors
2. Verify transaction was created
3. Check if land has owner_id

```sql
-- Verify transaction created
SELECT * FROM transaction WHERE listing_id = 'xxx';

-- Verify lands transferred
SELECT owner_id, price_base_bdt FROM land WHERE land_id IN (
    SELECT land_id FROM listing_land WHERE listing_id = 'xxx'
);
```

**Solution:**
- Check for error messages in logs
- Verify database is connected
- Restart application

### Issue: Wrong price increases

**Diagnosis:**
1. Calculate expected: `1,428.57 / owned_lands_count`
2. Compare with actual `price_base_bdt` change
3. Check if formula is being applied

```sql
-- Check recent transactions
SELECT * FROM transaction 
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC LIMIT 5;
```

**Solution:**
- Verify formula in code hasn't been modified
- Check that economy service is called after transaction

### Issue: Slow transaction response

**Diagnosis:**
1. Check database query performance
2. Count lands per biome

```sql
-- Biome with most lands
SELECT biome, COUNT(*) as land_count 
FROM land 
WHERE owner_id IS NOT NULL
GROUP BY biome 
ORDER BY land_count DESC;
```

**Solution:**
- Add database indexes on (biome, owner_id)
- Cache BiomeLandMarket data
- Optimize bulk update queries

## Reporting Issues

If verification fails:

1. **Collect evidence:**
   - Application logs (last 100 lines)
   - Database query results
   - Transaction ID from failed purchase
   - Expected vs actual prices

2. **Document issue:**
   - Steps to reproduce
   - Error messages
   - Database state
   - Expected behavior

3. **Debug:**
   - Check logs for "ERROR" and "Exception"
   - Verify database connectivity
   - Verify economy service initialization

## Success Criteria

✅ **System is working correctly when:**
1. All 7 biomes initialized in database
2. Buy transactions increase prices in all biomes
3. Prices follow formula: C / (7 × owned_lands_in_biome)
4. Zero-lands biomes skipped without errors
5. Negative prices prevented
6. Economy errors don't block transactions
7. Response times < 1 second
8. No SQL errors in logs

## Next Steps

Once verified:
1. ✅ Monitor in production for 1 week
2. ✅ Collect market statistics
3. ✅ Check for edge cases not covered
4. ✅ Optimize performance if needed
5. ✅ Document any issues found
6. ✅ Add API endpoints for market stats
7. ✅ Announce feature to players

---

**Verification Guide Complete**
Follow these steps to ensure the Global Biome Economy System is functioning correctly.
