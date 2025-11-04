# Automatic Land Allocation System

## Overview

The Virtual World platform automatically assigns a land plot to every new user upon registration. This document describes the implementation, configuration, and behavior of the land allocation system.

---

## Features

### 1. **Variable Land Sizes**

New users receive land plots with sizes following a weighted probability distribution:

- **36×36 units** (60% probability) - Most common, starter size
- **63×63 to 75×75 units** (30% probability) - Medium-sized plots
- **76×76 to 1000×1000 units** (10% probability) - Large plots with exponentially decreasing rarity

The largest sizes (e.g., 1000×1000) are extremely rare (~0.1% probability), creating excitement and variety in the user experience.

### 2. **Shape Variations**

Land plots have different geometric shapes:

- **Square** (95% probability) - Default shape, grid-aligned
- **Circle** (rare) - Inscribed in bounding square
- **Triangle** (rare) - Isosceles triangle
- **Rectangle** (rare) - Aspect ratios of 1.5:1 or 2:1

Non-square shapes add visual interest while remaining simple and fundamental.

### 3. **Intelligent Placement**

The system places new land plots using a smart adjacency algorithm:

- **Adjacent Placement**: New plots are placed next to existing lands, never isolated
- **No Overlap**: Strict validation ensures no coordinate conflicts
- **Buffer Spacing**: Configurable 1-unit buffer between plots prevents boundary issues
- **Scalable**: Uses PostgreSQL spatial indexes for efficient queries even with millions of users

### 4. **World Integration**

Land plots integrate seamlessly with the procedural world generation:

- Each land unit inherits biome, elevation, and color from world generation
- Pricing is calculated based on biome type
- Visual consistency with the infinite procedural world

---

## Architecture

### Database Schema

#### Lands Table Extensions

```sql
-- New columns added to lands table
shape          LandShape NOT NULL DEFAULT 'square'  -- enum: square, circle, triangle, rectangle
width          INTEGER   NOT NULL DEFAULT 1          -- land width in units
height         INTEGER   NOT NULL DEFAULT 1          -- land height in units
```

#### Admin Configuration

```sql
-- New admin_config columns for land allocation
starter_land_enabled              BOOLEAN DEFAULT true
starter_land_min_size             INTEGER DEFAULT 36
starter_land_max_size             INTEGER DEFAULT 1000
starter_land_buffer_units         INTEGER DEFAULT 1
starter_shape_variation_enabled   BOOLEAN DEFAULT true
```

### Service Architecture

```
┌─────────────────────────────────────────┐
│   User Registration Endpoint            │
│   (auth.py)                              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   LandAllocationService                  │
│   (land_allocation_service.py)           │
├─────────────────────────────────────────┤
│  • Select size (weighted random)         │
│  • Select shape (95% square, 5% other)   │
│  • Find adjacent position                │
│  • Validate no overlap with buffer       │
│  • Generate land records                 │
│  • Bulk insert to database               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   WorldGenerationService                 │
│   (world_service.py)                     │
├─────────────────────────────────────────┤
│  • Get biome at (x, y)                   │
│  • Get elevation at (x, y)               │
│  • Calculate base price                  │
└─────────────────────────────────────────┘
```

---

## Probability Distribution Details

### Size Distribution

```python
# Size probability breakdown:
36×36:      60.00%
63×63:      10.00%
69×69:      10.00%
75×75:      10.00%
100×100:     5.00%  ← Large sizes use exponential decay
150×150:     2.50%
200×200:     1.25%
300×300:     0.625%
500×500:     0.3125%
750×750:     0.15625%
1000×1000:   0.078125%  ← Extremely rare!
```

### Shape Distribution

```python
# Shape probability:
Square:      95%
Circle:       ~1.67%
Triangle:     ~1.67%
Rectangle:    ~1.67%
```

---

## Placement Algorithm

### Step-by-Step Process

1. **Check existing lands**
   - Query database for land count
   - If no lands exist → place at origin (0, 0)

2. **Calculate search area**
   - Find bounding box of all existing lands
   - Expand search area beyond boundaries

3. **Attempt placement** (max 100 attempts)
   - **First 50 attempts**: Try positions adjacent to boundaries
   - **Next 50 attempts**: Try random positions in search area
   - For each candidate position:
     - Check for overlap with buffer using spatial query
     - Return first valid position found

4. **Generate land units**
   - Create individual land records for each unit in the plot
   - Assign biome, elevation, color from world generation
   - Bulk insert all records

### Spatial Validation Query

```sql
-- Check if position (x, y, width, height) with buffer is valid
SELECT COUNT(*) FROM lands
WHERE lands.x < (x + width + buffer)
  AND (lands.x + lands.width) > (x - buffer)
  AND lands.y < (y + height + buffer)
  AND (lands.y + lands.height) > (y - buffer)

-- If count = 0, position is valid
```

---

## Configuration

### Admin Settings

Administrators can configure land allocation via the Admin Dashboard or API:

```json
{
  "starter_land_enabled": true,           // Enable/disable allocation
  "starter_land_min_size": 36,            // Minimum land size
  "starter_land_max_size": 1000,          // Maximum land size
  "starter_land_buffer_units": 1,         // Buffer spacing between plots
  "starter_shape_variation_enabled": true // Enable rare shapes
}
```

### Disabling Allocation

To disable automatic land allocation:

```python
# Via API (requires admin authentication)
PATCH /api/v1/admin/config
{
  "starter_land_enabled": false
}
```

---

## Testing

### Running Tests

```bash
cd backend
pytest tests/test_land_allocation.py -v
```

### Test Coverage

The test suite includes:

- ✅ Size distribution validation (statistical)
- ✅ Shape distribution validation
- ✅ Overlap detection
- ✅ Buffer spacing enforcement
- ✅ Adjacent placement verification
- ✅ Multiple user allocation
- ✅ Edge cases (disabled allocation, no existing lands)

### Example Test Output

```
test_land_allocation.py::TestSizeDistribution::test_size_selection_distribution PASSED
test_land_allocation.py::TestSizeDistribution::test_largest_sizes_are_rarest PASSED
test_land_allocation.py::TestShapeDistribution::test_shape_selection_distribution PASSED
test_land_allocation.py::TestPlacementAlgorithm::test_first_land_at_origin PASSED
test_land_allocation.py::TestPlacementAlgorithm::test_no_overlap_validation PASSED
test_land_allocation.py::TestPlacementAlgorithm::test_buffer_spacing PASSED
test_land_allocation.py::TestEndToEndAllocation::test_allocate_starter_land PASSED
test_land_allocation.py::TestEndToEndAllocation::test_multiple_users_allocation PASSED
```

---

## Performance Considerations

### Scalability

The system is designed to scale to millions of users:

1. **Spatial Indexes**: PostgreSQL BRIN indexes enable O(log n) spatial queries
2. **Bulk Insertion**: All land units inserted in single transaction
3. **Cached Boundaries**: Bounding box queries use aggregates for efficiency
4. **Limited Attempts**: Max 100 placement attempts prevents infinite loops

### Optimization Strategies

For production at scale:

1. **Cache Frontier Zones** in Redis
   - Store available placement regions
   - Update asynchronously as lands are allocated

2. **Batch Pre-allocation**
   - Pre-generate valid positions during off-peak hours
   - Assign from pool during registration

3. **Partitioned Tables**
   - Partition lands table by coordinate ranges
   - Improves query performance for spatial lookups

### Expected Performance

- **First user**: ~50ms (place at origin)
- **100 users**: ~150ms average (some placement attempts)
- **10,000 users**: ~300ms average (more attempts needed)
- **1,000,000 users**: ~500ms average (with optimizations)

---

## API Integration

### Registration with Land Allocation

```javascript
// User registration automatically includes land allocation
POST /api/v1/auth/register
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "SecurePassword123!"
}

// Response includes user data
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "alice",
  "email": "alice@example.com",
  "balance_bdt": 0,
  // ...
}

// Land is allocated asynchronously in background
// Check user's lands via:
GET /api/v1/users/{user_id}/lands
```

### Querying Allocated Land

```javascript
GET /api/v1/users/{user_id}/lands

// Response
{
  "lands": [
    {
      "land_id": "...",
      "coordinates": { "x": 51, "y": 0, "z": 0 },
      "shape": "square",
      "width": 36,
      "height": 36,
      "biome": "plains",
      "elevation": 0.523,
      "color_hex": "#7ba62a",
      "for_sale": false,
      "price_base_bdt": 1000
    },
    // ... 36×36 = 1,296 land units total
  ],
  "total": 1296,
  "plot_info": {
    "shape": "square",
    "dimensions": "36×36",
    "total_area": 1296,
    "location": "(51, 0)"
  }
}
```

---

## Frontend Integration

### Displaying Land Shapes

The frontend needs to render different land shapes:

```javascript
// In WorldRenderer component
renderLandPlot(land) {
  switch (land.shape) {
    case 'square':
      return this.renderSquare(land);
    case 'circle':
      return this.renderCircle(land);
    case 'triangle':
      return this.renderTriangle(land);
    case 'rectangle':
      return this.renderRectangle(land);
  }
}
```

### Visual Indicators

- **Ownership Highlight**: User's own land highlighted in UI
- **Shape Borders**: Non-square shapes have visible borders
- **Size Badge**: Display land size (e.g., "36×36") on hover

---

## Troubleshooting

### Common Issues

#### 1. **Land allocation fails**

**Symptom**: Registration succeeds but no land allocated

**Causes**:
- `starter_land_enabled = false` in config
- Database connection timeout
- No valid positions found after 100 attempts

**Solutions**:
- Check admin config settings
- Review database logs for errors
- Increase `max_attempts` if world is very crowded

#### 2. **Overlapping lands detected**

**Symptom**: Multiple users own same coordinates

**Causes**:
- Race condition in concurrent registrations
- Buffer validation bug

**Solutions**:
- Add database unique constraint on (x, y, z)
- Use distributed locks (Redis) for placement

#### 3. **Lands placed far from others**

**Symptom**: New lands appear isolated

**Causes**:
- Bounding box calculation error
- Random position selection in second half of attempts

**Solutions**:
- Review placement algorithm logs
- Reduce search area expansion factor

---

## Future Enhancements

### Planned Features

1. **Land Trading**
   - Allow users to trade/sell allocated land
   - Marketplace integration

2. **Land Upgrades**
   - Expand plot boundaries
   - Merge adjacent plots

3. **Premium Allocation**
   - Paid users get larger starting plots
   - Choose preferred biome/location

4. **Land Leasing**
   - Temporary land rentals
   - Time-limited ownership

5. **Custom Shapes**
   - User-defined plot boundaries
   - Complex polygonal shapes

### Performance Improvements

1. **Parallel Placement**
   - Allocate multiple users concurrently
   - Lock-free optimistic placement

2. **Smart Zoning**
   - Pre-defined regions for new users
   - Density-based allocation

3. **Predictive Allocation**
   - Machine learning to predict high-demand areas
   - Dynamic sizing based on activity

---

## Conclusion

The automatic land allocation system provides every new user with a unique, fairly-distributed land plot, creating immediate engagement and ownership in the virtual world. The implementation balances randomness with fairness, ensuring variety while maintaining system stability and performance at scale.

For questions or issues, contact the development team or file an issue in the project repository.

---

**Version**: 1.0.0
**Last Updated**: 2025-11-04
**Author**: VirtualWorld Development Team
