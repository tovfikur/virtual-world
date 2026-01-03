# Global Biome Economy System - Quick Reference

## What It Does

Dynamic land prices across all 7 biomes based on buy/sell activity.

## The Formula

When someone buys land for C BDT:
```
Price increase per land in biome i = C ÷ 7 ÷ (number of owned lands in biome i)
```

Example: $10,000 purchase
- Plains (50 owned lands): +$28.57 per land
- Beach (30 owned lands): +$47.62 per land
- Forest (100 owned lands): +$14.29 per land
- etc. for all 7 biomes

When someone sells land for C BDT, same formula but subtract (prices decrease).

## Core Files

| File | Purpose |
|------|---------|
| `backend/app/models/biome_land_market.py` | BiomeLandMarket model - tracks per-biome state |
| `backend/app/services/biome_land_economy_service.py` | BiomeLandEconomyService - price adjustment logic |
| `backend/app/services/marketplace_service.py` | Integration in buy_now() and finalize_auction() |
| `backend/app/main.py` | Initialization on app startup |

## Key Methods

```python
# Initialize markets (runs on app startup)
await BiomeLandEconomyService.initialize_markets(db)

# Handle purchase (called after transaction completes)
await BiomeLandEconomyService.handle_land_purchase(
    db, land_id, amount_paid_bdt, buyer_id, seller_id
)

# Handle sale (called when land is sold)
await BiomeLandEconomyService.handle_land_sale(
    db, land_id, amount_received_bdt, seller_id
)

# Get market stats
stats = await BiomeLandEconomyService.get_biome_market_stats(db)
```

## How It Integrates

### Buy Now Flow
1. Player buys land in marketplace (fixed price)
2. Lands transfer, funds exchanged
3. **Economy system calls handle_land_purchase()**
4. All biome prices updated proportionally
5. BiomeLandMarket statistics updated

### Auction Flow
1. Auction ends, highest bid wins
2. Lands transfer, funds exchanged
3. **Economy system calls handle_land_purchase()**
4. All biome prices updated proportionally
5. BiomeLandMarket statistics updated

### Sell Flow
Currently marketplace only has buy listings. When sell listings are implemented:
1. Player lists land for sale
2. Buyer purchases
3. **Economy system calls handle_land_sale()**
4. All biome prices decrease proportionally

## Edge Cases

| Case | Behavior | Why |
|------|----------|-----|
| Biome has 0 owned lands | Skip price update for that biome | Avoid division by zero |
| Price would go negative | Cap at 0 | Prices can't be negative |
| Concurrent transactions | Handled by database locks | SQLAlchemy with_for_update() |
| Transaction fails | Automatic rollback | Single async session |

## Impact on Players

**Price Discovery**
- Prices reflect real market activity
- High demand (many purchases) → prices rise
- Low demand (many sales) → prices fall
- Fair market mechanism

**Opportunity**
- Early movers in cheap biome can profit as prices rise
- Speculators can buy low, sell high
- Equilibrium pricing over time

**Volatility**
- Large purchases/sales cause big swings
- Fragmented markets (few lands) more volatile
- Consolidated markets (many lands) more stable

## Configuration

Currently all economy parameters are hardcoded:

| Parameter | Value | Location |
|-----------|-------|----------|
| Number of biomes | 7 | TOTAL_BIOMES constant |
| Price formula | C / (X × Xi) | Formula in handle_land_purchase() |
| Minimum price | 0 (can't go negative) | max(0, ...) in handle_land_sale() |

**Future Enhancement**: Make these configurable in AdminConfig

## Monitoring

Check logs for economy operations:

```
DEBUG: Biome economy updated: {...}
INFO: Land purchase processed: land_id, Amount: X BDT
ERROR: Error processing land purchase: ...
```

Check database:
```sql
SELECT * FROM biome_land_market;
```

## Testing Checklist

- [ ] Buy land for 10,000 BDT
  - [ ] All 7 biome prices increased
  - [ ] BiomeLandMarket.last_transaction_at updated
- [ ] Sell land for 5,000 BDT
  - [ ] All 7 biome prices decreased
  - [ ] Prices don't go negative
- [ ] Buy in biome with 0 owned lands
  - [ ] Other biomes still update
  - [ ] Zero-lands biome skipped (expected)
- [ ] Run auction and finalize
  - [ ] Economy system triggered
  - [ ] Prices updated correctly
- [ ] Check logs
  - [ ] No errors
  - [ ] Debug messages show details

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Prices not updating | Check logs for errors, verify transaction completed |
| Market stats wrong | Check BiomeLandMarket for stale data |
| Division by zero error | Verify handle_land_sale() skips zero-lands biomes |
| Negative prices | Check max() in handle_land_sale() is working |
| Slow transaction response | Monitor database query times, consider caching |

## Next Steps

1. **Sold Lands Tracking**: Implement automatic update of BiomeLandMarket.sold_lands_count when lands are claimed/transferred
2. **Frontend Dashboard**: Expose biome market stats via new API endpoints
3. **Admin Controls**: Add economy parameters to admin dashboard
4. **Historical Data**: Track price history for analytics
5. **Price Floor/Ceiling**: Add admin-configurable limits

## Related Documentation

- [Full Implementation Guide](BIOME_ECONOMY_IMPLEMENTATION.md)
- [Trading System Documentation](BIOME_TRADING_SYSTEM_COMPLETE.md)
- [Database Schema](06_DATABASE_SCHEMA.md)
- [Marketplace API](20_MARKETPLACE_API.md)
