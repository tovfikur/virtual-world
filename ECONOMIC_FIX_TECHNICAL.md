# Economic Settings Price Recalculation - Implementation Details

## Overview

The economic settings fix ensures that land prices are always calculated based on the current admin configuration, rather than returning stale prices stored in the database.

## Architecture

### Price Calculation Flow

```
Frontend Request
    ↓
API Endpoint (lands.py or chunks.py)
    ↓
Fetch Land Data from Database
    ↓
Calculate Current Price Based on Admin Config
    ├─ Fetch AdminConfig
    ├─ Get Biome Base Price
    ├─ Apply Elevation Factor
    └─ Return: int(base * elevation_factor)
    ↓
Return Response with Current Price
    ↓
Frontend Displays Price
```

## Code Changes

### 1. Lands Endpoint (`backend/app/api/v1/endpoints/lands.py`)

#### Added Function: `_calculate_current_land_price()`

```python
async def _calculate_current_land_price(
    land: Land,
    db: AsyncSession
) -> int:
    """
    Recalculate land price based on current admin configuration.

    Formula:
        elevation_factor = min_factor + (elevation * (max_factor - min_factor))
        price = base_price * elevation_factor
    """
```

**Parameters:**

- `land: Land` - ORM object with biome and elevation
- `db: AsyncSession` - Database session to fetch AdminConfig

**Returns:**

- `int` - Calculated price in BDT

**Logic:**

1. Fetch AdminConfig from database
2. Map biome to base price (plains, forest, beach, etc.)
3. Clamp elevation to [0, 1] range
4. Calculate elevation factor using min/max factors
5. Return: `int(base_price * elevation_factor)`

#### Updated Function: `_serialize_land()`

Added price recalculation:

```python
# Recalculate price based on current admin config
try:
    current_price = await _calculate_current_land_price(land, db)
    land_dict["price_base_bdt"] = current_price
except Exception as e:
    logger.warning(f"Failed to recalculate land price for {land.land_id}: {e}")
    # Keep the stored price if calculation fails
```

**Fallback Logic:**

- If calculation fails, keeps the stored `price_base_bdt` from database
- Logs warning for monitoring

### 2. Chunks Endpoint (`backend/app/api/v1/endpoints/chunks.py`)

#### Added Function: `_calculate_unclaimed_land_price()`

Similar to lands endpoint but works with dictionaries instead of ORM objects:

```python
async def _calculate_unclaimed_land_price(
    land_data: Dict,
    db: AsyncSession
) -> int:
    """
    Recalculate unclaimed land price based on current admin configuration.
    """
```

**Key Differences:**

- Works with `Dict` instead of `Land` ORM object
- Converts biome string to enum: `biome = Biome(biome_str)`
- Handles missing values with defaults

#### Updated Function: `enrich_chunk_with_ownership()`

Added price recalculation in the loop:

```python
# Recalculate price based on current admin config for both owned and unowned lands
try:
    current_price = await _calculate_unclaimed_land_price(land, db)
    land["price_base_bdt"] = current_price
except Exception as e:
    logger.warning(f"Failed to recalculate price for land at ({land['x']}, {land['y']}): {e}")
    # Keep the generated price if calculation fails
```

## Affected API Endpoints

### Lands Endpoints (now return current prices)

| Endpoint                              | Method | Affected          |
| ------------------------------------- | ------ | ----------------- |
| `/lands/{land_id}`                    | GET    | ✅ Yes            |
| `/lands/coordinates/{x}/{y}`          | GET    | ✅ Yes            |
| `/lands/owner/{owner_id}/coordinates` | GET    | ✅ Yes            |
| `/lands/`                             | GET    | ✅ Yes (search)   |
| `/lands/{land_id}`                    | PUT    | ✅ Yes (response) |
| `/lands/{land_id}/fence`              | POST   | ✅ Yes (response) |
| `/lands/{land_id}/transfer`           | POST   | ✅ Yes (response) |
| `/lands/claim`                        | POST   | ✅ Yes (response) |

### Chunk Endpoints (now return current prices)

| Endpoint                      | Method | Affected |
| ----------------------------- | ------ | -------- |
| `/chunks/{chunk_x}/{chunk_y}` | GET    | ✅ Yes   |
| `/chunks/batch`               | POST   | ✅ Yes   |

## Price Calculation Details

### Formula

```
elevation_factor = min_factor + (elevation * (max_factor - min_factor))
price = base_price * elevation_factor
```

### Example Calculation

```
Given:
- Plains base price: 125 BDT
- Elevation: 0.5
- Min factor: 0.8
- Max factor: 1.2

Calculation:
elevation_factor = 0.8 + (0.5 * (1.2 - 0.8)) = 0.8 + 0.2 = 1.0
price = 125 * 1.0 = 125 BDT
```

### Edge Cases Handled

1. **Missing AdminConfig**
   - Falls back to stored price
2. **Invalid biome**

   - Defaults to PLAINS price

3. **Elevation out of range**

   - Clamped to [0, 1]

4. **Min factor > Max factor**

   - Swapped to ensure correct order

5. **Database error**
   - Exception caught, logged, stored price returned

## Performance Considerations

### Database Queries

- **Per land response**: 1 query to fetch AdminConfig
- **Per chunk response**: 1 query to fetch AdminConfig (shared across all lands in chunk)
- No N+1 problem since AdminConfig is single record

### Caching Opportunities

If performance becomes an issue, could optimize with:

```python
# Option 1: Cache AdminConfig in Redis
cache_key = "admin_config:economy"
config = await cache_service.get(cache_key)
if not config:
    config = await db.execute(select(AdminConfig).limit(1))
    await cache_service.set(cache_key, config, ttl=300)  # 5 minutes

# Option 2: Cache at application startup (less flexible)
# Load once in app initialization, invalidate on admin update
```

## Testing Strategy

### Unit Tests

```python
# Test price calculation logic
async def test_calculate_land_price_with_admin_config():
    # Setup AdminConfig with known values
    # Create Land with known elevation
    # Calculate price
    # Assert result matches formula
    pass

# Test fallback to stored price
async def test_price_calculation_failure_fallback():
    # Make DB unavailable for AdminConfig
    # Calculate price
    # Assert returns stored price
    pass
```

### Integration Tests

```python
# Test via API endpoint
async def test_get_land_returns_current_price():
    # Admin updates base price
    # GET /lands/{land_id}
    # Assert response price matches admin config
    pass

# Test chunk endpoint
async def test_chunk_prices_reflect_admin_config():
    # Admin updates base price
    # GET /chunks/{x}/{y}
    # Assert all lands in chunk have current price
    pass
```

### Manual Testing

1. Set known admin price
2. Fetch land via API
3. Verify price matches formula
4. Change admin config
5. Verify price updates immediately

## Error Handling

### Logging

- WARNING: "Failed to recalculate land price for {land_id}: {error}"
- WARNING: "Failed to recalculate price for land at ({x}, {y}): {error}"

### Fallback Behavior

- Always returns a price (either calculated or stored)
- Never raises exception from price calculation
- Logs issue for monitoring

## Backwards Compatibility

✅ **Fully compatible:**

- API contract unchanged
- Response field names unchanged
- Only value of `price_base_bdt` changes (to be current)
- Existing clients unaffected

## Future Enhancements

1. **Add cache invalidation**

   - When admin updates config, clear price cache

2. **Add price history**

   - Track price changes over time for analytics

3. **Add price prediction**

   - ML model to predict optimal prices

4. **Batch price calculation**

   - Single DB query for multiple lands

5. **Price range limits**
   - Add admin config for min/max price bounds

## Related Files

- **Configuration:** `backend/app/models/admin_config.py` (biome price fields)
- **Schema:** `backend/app/schemas/land_schema.py` (LandResponse)
- **Frontend:** `frontend/src/components/LandInfoPanel.jsx` (price display)
- **Frontend:** `frontend/src/components/MultiLandActionsPanel.jsx` (total price)

## Debugging

### Check current admin config

```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8000/api/v1/admin/config/economy
```

### Check land price from API

```bash
curl http://localhost:8000/api/v1/lands/{land_id}
# Check: response.price_base_bdt should match formula
```

### Check calculation manually

```python
# In Python REPL
base = 125
elevation = 0.5
min_factor = 0.8
max_factor = 1.2
elevation_factor = min_factor + (elevation * (max_factor - min_factor))
price = int(base * elevation_factor)
print(f"Calculated price: {price}")  # Should be 125
```
