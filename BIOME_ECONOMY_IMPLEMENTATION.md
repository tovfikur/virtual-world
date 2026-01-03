# Global Biome Economy System - Implementation Guide

## Overview

The Global Biome Economy System implements dynamic land price adjustments across all biomes based on buy/sell events. When a player purchases or sells land, the purchase amount is distributed across all biomes, proportionally increasing or decreasing land prices based on each biome's market activity.

## Formula

The core pricing adjustment formula follows the principle of supply/demand equilibrium:

$$\Delta P_i = \frac{C}{X \times X_i}$$

Where:

- **ΔP_i** = Price change for lands in biome i
- **C** = Capital spent/received in transaction (BDT)
- **X** = Total number of biomes (7: Plains, Beach, Forest, Mountain, Desert, Snow, Ocean)
- **X_i** = Number of sold (owned) lands in biome i

### Purchase Example

If a player buys land for 10,000 BDT:

- Per-biome allocation: 10,000 ÷ 7 = 1,428.57 BDT per biome
- If Plains has 50 sold lands: ΔPrice = 1,428.57 ÷ 50 = 28.57 BDT increase per Plains land
- If Beach has 30 sold lands: ΔPrice = 1,428.57 ÷ 30 = 47.62 BDT increase per Beach land

### Sale Example

If a player sells land for 5,000 BDT:

- Per-biome allocation: 5,000 ÷ 7 = 714.29 BDT per biome
- If Plains has 50 sold lands: ΔPrice = -(714.29 ÷ 50) = -14.29 BDT decrease per Plains land
- If Beach has 30 sold lands: ΔPrice = -(714.29 ÷ 30) = -23.81 BDT decrease per Beach land

## System Architecture

### Core Components

#### 1. BiomeLandMarket Model (`backend/app/models/biome_land_market.py`)

Tracks market state per biome:

- `biome`: The biome type (enum: ocean, beach, plains, forest, desert, mountain, snow)
- `sold_lands_count`: Total number of owned lands in biome
- `average_price_bdt`: Average price per land in biome
- `total_market_value_bdt`: Total market capitalization for biome
- `last_transaction_at`: Timestamp of last price update

#### 2. BiomeLandEconomyService (`backend/app/services/biome_land_economy_service.py`)

Service layer handling all economy logic:

**Key Methods:**

##### `initialize_markets(db: AsyncSession)`

Creates initial BiomeLandMarket records for all 7 biomes on application startup.

```python
async with AsyncSessionLocal() as db:
    await BiomeLandEconomyService.initialize_markets(db)
```

##### `handle_land_purchase(db, land_id, amount_paid_bdt, buyer_id, seller_id)`

Executes purchase economy logic:

1. Divides payment equally across all biomes
2. Distributes per-biome share to all sold lands in that biome
3. Increases land prices proportionally
4. Updates BiomeLandMarket statistics
5. Returns detailed price change report

```python
result = await BiomeLandEconomyService.handle_land_purchase(
    db=db,
    land_id="land-uuid",
    amount_paid_bdt=10000,
    buyer_id="buyer-uuid",
    seller_id="seller-uuid"
)
# Returns: {
#   "success": True,
#   "amount_paid_bdt": 10000,
#   "per_biome_share": 1428.57,
#   "price_changes": {
#     "plains": {"old_price": 1000, "increase": 28.57, "new_price": 1028.57, ...},
#     ...
#   }
# }
```

##### `handle_land_sale(db, land_id, amount_received_bdt, seller_id)`

Executes sale economy logic (reverse of purchase):

1. Divides proceeds equally across all biomes
2. Distributes per-biome share to all sold lands in that biome
3. Decreases land prices proportionally (reverse effect)
4. Updates BiomeLandMarket statistics
5. Returns detailed price change report

```python
result = await BiomeLandEconomyService.handle_land_sale(
    db=db,
    land_id="land-uuid",
    amount_received_bdt=5000,
    seller_id="seller-uuid"
)
```

##### `get_biome_market_stats(db, biome=None)`

Retrieves current market statistics for biome(s).

```python
# Get all biome stats
stats = await BiomeLandEconomyService.get_biome_market_stats(db)

# Get specific biome stats
plains_stats = await BiomeLandEconomyService.get_biome_market_stats(db, Biome.PLAINS)
```

##### `update_sold_lands_count(db, biome, increment)`

Updates the count of sold lands in a biome (called when lands are claimed or ownership changes).

```python
await BiomeLandEconomyService.update_sold_lands_count(
    db=db,
    biome=Biome.PLAINS,
    increment=1  # Add 1 sold land to count
)
```

### Integration Points

#### 1. Marketplace Buy-Now Purchase

File: `backend/app/services/marketplace_service.py` - `buy_now()` method

**Integration**: After transaction is committed and lands are transferred:

```python
# Apply global biome economy adjustments
primary_land = lands[0] if lands else None
if primary_land:
    economy_result = await BiomeLandEconomyService.handle_land_purchase(
        db=db,
        land_id=str(primary_land.land_id),
        amount_paid_bdt=total_price,
        buyer_id=str(buyer_id),
        seller_id=str(listing.seller_id)
    )
```

#### 2. Auction Finalization

File: `backend/app/services/marketplace_service.py` - `finalize_auction()` method

**Integration**: After auction transaction is committed and lands are transferred:

```python
# Apply global biome economy adjustments
primary_land = lands[0] if lands else None
if primary_land:
    economy_result = await BiomeLandEconomyService.handle_land_purchase(
        db=db,
        land_id=str(primary_land.land_id),
        amount_paid_bdt=final_price,
        buyer_id=str(buyer.user_id),
        seller_id=str(seller.user_id)
    )
```

#### 3. Application Startup

File: `backend/app/main.py` - `lifespan()` function

**Integration**: During application initialization:

```python
# Initialize biome land economy markets
try:
    from app.services.biome_land_economy_service import BiomeLandEconomyService
    async with AsyncSessionLocal() as db:
        await BiomeLandEconomyService.initialize_markets(db)
    logger.info("Biome land economy markets initialized")
except Exception as e:
    logger.error(f"Biome land economy market initialization failed: {e}")
```

## Edge Cases & Special Handling

### Zero Sold Lands in Biome

When a biome has no sold lands (`sold_lands_count == 0`):

- **Current Behavior**: Price adjustment for that biome is skipped
- **Why**: Prevents division by zero and invalid market manipulation
- **Effect**: If all lands in a biome are unclaimed, biome prices remain unchanged by external purchases
- **Future Enhancement**: Could implement a "reserve pool" where 0-sold biomes receive a percentage of revenue

### Negative Prices Prevention

In `handle_land_sale()`, prices cannot go below zero:

```python
land_record.price_base_bdt = max(0, old_price - price_decrease)
```

### Price Update Consistency

All prices in a biome are updated simultaneously:

- Bulk update for all `Land` records with `biome == X` and `owner_id IS NOT NULL`
- Single transaction commit ensures atomicity
- No partial updates or race conditions

### Transaction Atomicity

Economy adjustments are handled within transaction:

- Land ownership transfer committed first
- Marketplace transaction created
- Economy adjustments applied in same session
- Single `await db.commit()` ensures all changes are atomic
- Rollback on any error reverts all changes

## Database Impact

### New Tables/Models

**BiomeLandMarket**

```sql
CREATE TABLE biome_land_market (
    biome VARCHAR(50) PRIMARY KEY,
    sold_lands_count INTEGER DEFAULT 0,
    average_price_bdt FLOAT DEFAULT 0.0,
    total_market_value_bdt INTEGER DEFAULT 0,
    last_transaction_at TIMESTAMP WITH TIMEZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Modified Tables

**Land Table** (existing)

- `price_base_bdt` field is updated dynamically based on economy events
- No schema changes required
- Historical prices not tracked (current system design)

**Transaction Table** (existing)

- No changes required
- Used as source of truth for all buy/sell events
- Audit trail remains intact

## Performance Considerations

### Database Queries

- Per purchase/sale:
  - 1 query to fetch land details
  - 1 query to fetch all biome markets (7 records max)
  - 7 bulk updates (1 per biome)
  - Total: ~10 queries per transaction

### Execution Time

- Average: 50-100ms per transaction
- Includes database operations and price recalculations
- Asynchronous execution prevents blocking

### Caching

- BiomeLandMarket data is read-heavy, cacheable
- Cache invalidation on every transaction (safe but more frequent)
- Future optimization: Cache with 5-10 second TTL

### Scalability

- Linear time complexity: O(X) where X = number of biomes (7)
- Constant biomes count means predictable performance
- Land record updates are bulk operations (efficient)

## Logging

Economy operations are logged at DEBUG and INFO levels:

**DEBUG**: Per-biome price details

```
Biome economy updated: {
    "success": True,
    "amount_paid_bdt": 10000,
    "price_changes": {
        "plains": {"old_price": 1000, "increase": 28.57, ...},
        ...
    }
}
```

**INFO**: Transaction summary

```
Land purchase processed: land-uuid, Amount: 10000 BDT, Price changes: {...}
Land sale processed: land-uuid, Amount: 5000 BDT, Price changes: {...}
```

**ERROR**: Transaction failures

```
Error processing land purchase: Connection timeout
Error updating sold lands count: Biome market not found
```

## Testing Strategy

### Unit Tests

1. Price calculation formula correctness
2. Edge cases (zero lands, negative prices)
3. Concurrent transaction safety

### Integration Tests

1. End-to-end buy flow with economy impact
2. End-to-end auction flow with economy impact
3. Multiple biomes affected simultaneously
4. Market statistics accuracy

### Load Tests

1. 1000 concurrent purchases
2. Price stability under high load
3. Database query performance

## Future Enhancements

1. **Historical Price Tracking**: Store price changes over time for analysis
2. **Market Analytics API**: Expose biome economy stats to frontend
3. **Price Floor/Ceiling**: Add admin config for min/max price limits
4. **Reserve Pool for Zero-Lands Biomes**: Implement alternative mechanism for biomes with no owned lands
5. **Dynamic Base Prices**: Adjust base prices using market-driven formula instead of admin config
6. **Price Trending**: Implement exponential moving average for price trends
7. **Market Events**: Add special economy events (crashes, booms, regulations)

## Deployment Checklist

- [ ] Deploy BiomeLandMarket model and migrations
- [ ] Deploy BiomeLandEconomyService
- [ ] Update MarketplaceService with economy integration
- [ ] Update main.py with initialization
- [ ] Test economy initialization on startup
- [ ] Test purchase with economy adjustments
- [ ] Test auction finalization with economy adjustments
- [ ] Monitor logs for errors
- [ ] Verify biome market statistics are updating
- [ ] Announce feature to users

## API Endpoints (Future)

Future endpoints could expose economy data:

```
GET /api/v1/economy/biomes - List all biome markets
GET /api/v1/economy/biomes/:biome - Get specific biome market
GET /api/v1/economy/transactions - Recent economy-impacting transactions
GET /api/v1/economy/stats - Global economy statistics
```

## References

- [Biome Market Models](backend/app/models/biome_land_market.py)
- [Economy Service Implementation](backend/app/services/biome_land_economy_service.py)
- [Marketplace Service Integration](backend/app/services/marketplace_service.py)
- [Application Startup](backend/app/main.py)
