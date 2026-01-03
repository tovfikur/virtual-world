# Economic Settings Price Recalculation Fix

## Problem
Economic settings (biome base prices, elevation factors) were not being reflected in the frontend when:
1. Admin updated economic configuration
2. Users browsed the world and selected land for buy/sell
3. Multi-select showing land prices

The issue was that prices were stored in the database when lands were created/claimed, but were never recalculated when the admin updated the configuration.

## Root Cause
- Land prices were calculated at generation time based on admin config at that moment
- Stored in `lands.price_base_bdt` column
- When admin updated config, API endpoints returned stale prices from the database
- Frontend displayed the old stored prices instead of current prices

## Solution Implemented

### 1. **Lands Endpoint** (`backend/app/api/v1/endpoints/lands.py`)

**Added `_calculate_current_land_price()` function:**
- Fetches current admin configuration
- Recalculates land price based on current biome base prices and elevation factors
- Applied to all land responses

**Updated `_serialize_land()` function:**
- Now calls `_calculate_current_land_price()` after serializing land data
- All land API calls return current prices reflecting admin's latest settings

### 2. **Chunks Endpoint** (`backend/app/api/v1/endpoints/chunks.py`)

**Added `_calculate_unclaimed_land_price()` function:**
- Similar price calculation for unclaimed/unowned lands from chunk generation
- Works with land data dictionaries instead of ORM objects

**Updated `enrich_chunk_with_ownership()` function:**
- Recalculates prices for all lands in chunks (both owned and unowned)
- Ensures world view displays current prices

## How It Works

### Price Calculation Formula
```
base_price = biome_specific_base_price (from admin config)
elevation_factor = min_factor + (elevation * (max_factor - min_factor))
final_price = base_price * elevation_factor
```

Where:
- `biome_specific_base_price` = Admin's configured price for the biome (plains, forest, etc.)
- `elevation` = Land's elevation value (0-1)
- `min_factor` & `max_factor` = Admin's configured elevation price factors

### Affected Endpoints

**Land retrieval (now recalculates price):**
- `GET /lands/{land_id}` - Get land by ID
- `GET /lands/coordinates/{x}/{y}` - Get land by coordinates  
- `GET /lands/` - Search/filter lands
- `GET /lands/owner/{owner_id}/coordinates` - Get owner's lands

**Chunk streaming (now recalculates price):**
- `GET /chunks/{chunk_x}/{chunk_y}` - Get single chunk
- `POST /chunks/batch` - Get multiple chunks

**Frontend components updated:**
- `LandInfoPanel` - Shows correct current price when land is selected
- `MultiLandActionsPanel` - Shows correct total price for bulk purchase
- `WorldPage` - Displays current prices in land information

## Configuration

Admin can update economic settings via:
- **Admin Dashboard** → Economy Settings
- **API Endpoint**: `PATCH /admin/config/economy`

**Configurable fields:**
- `plains_base_price` - Base price for plains biome
- `forest_base_price` - Base price for forest biome
- `beach_base_price` - Base price for beach biome
- `mountain_base_price` - Base price for mountain biome
- `desert_base_price` - Base price for desert biome
- `snow_base_price` - Base price for snow biome
- `ocean_base_price` - Base price for ocean biome
- `elevation_price_min_factor` - Price factor at elevation 0
- `elevation_price_max_factor` - Price factor at elevation 1

## Testing Checklist

1. ✅ Update biome base price in admin panel
2. ✅ Navigate to world and select a land of that biome
3. ✅ Verify price in LandInfoPanel reflects new price
4. ✅ Multi-select multiple lands and verify total price is correct
5. ✅ Try to buy land - should charge at current price, not old price
6. ✅ Update elevation factors and verify price changes accordingly
7. ✅ Select multiple lands of different biomes - each should calculate correctly

## Performance Considerations

- Price recalculation happens per-request when fetching land data
- AdminConfig is fetched from database (not cached) to ensure latest settings
- Fallback to stored price if config fetch fails
- For bulk operations (multi-select), small query overhead is acceptable

## Backwards Compatibility

✅ **No breaking changes:**
- Existing API contracts unchanged
- Response format identical
- Price field name unchanged (`price_base_bdt`)
- Fallback to stored price if admin config missing

## Future Optimizations

1. **Cache admin config** - Could cache AdminConfig with short TTL (e.g., 1 minute) to reduce DB queries
2. **Batch price calculation** - Could optimize batch chunk requests with single DB query
3. **Database trigger** - Could store calculated price in DB on-demand for reporting
