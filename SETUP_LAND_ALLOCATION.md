# Land Allocation System Setup Guide

## After Fresh Database Setup (docker-compose down -v)

When you run `docker-compose down -v`, all volumes are deleted including the database. You need to reinitialize the `admin_config` table for land allocation to work.

---

## Quick Setup Steps

### Option 1: Manual SQL (Fastest)

```bash
# 1. Start containers
docker-compose up -d

# 2. Wait for services to be ready (check with docker-compose ps)

# 3. Get a user ID (register a user first if needed)
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "SELECT user_id FROM users LIMIT 1;"

# 4. Insert admin config (replace USER_ID with actual UUID from step 3)
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
INSERT INTO admin_config (
  config_id, world_seed, noise_frequency, noise_octaves, noise_persistence, noise_lacunarity,
  biome_forest_percent, biome_grassland_percent, biome_water_percent, biome_desert_percent, biome_snow_percent,
  base_land_price_bdt, forest_multiplier, grassland_multiplier, water_multiplier, desert_multiplier, snow_multiplier,
  transaction_fee_percent, starter_land_enabled, starter_land_min_size, starter_land_max_size,
  starter_land_buffer_units, starter_shape_variation_enabled, updated_by_id, created_at, updated_at
) VALUES (
  gen_random_uuid(), 12345, 0.05, 6, 0.6, 2.0,
  0.2, 0.2, 0.2, 0.2, 0.2,
  1000, 1.0, 0.8, 1.2, 0.7, 1.5,
  5.0, true, 36, 1000,
  1, true, 'USER_ID', NOW(), NOW()
);"
```

### Option 2: Python Script (Automated)

```bash
# 1. Start containers
docker-compose up -d

# 2. Register at least one user (via UI or curl)

# 3. Run initialization script
docker-compose exec backend python init_admin_config.py
```

---

## Verification

Check if admin config exists:

```bash
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
  SELECT starter_land_enabled, starter_land_min_size, starter_land_max_size
  FROM admin_config;
"
```

Expected output:
```
 starter_land_enabled | starter_land_min_size | starter_land_max_size
----------------------+-----------------------+-----------------------
 t                    |                    36 |                  1000
```

---

## Test Land Allocation

Register a new user via API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@test.com", "password": "TestPassword123!"}'
```

Check backend logs:

```bash
docker-compose logs backend --tail=20 | grep "Allocat"
```

Expected output:
```
app.services.land_allocation_service - INFO - Allocating square land 36x36 to user testuser
app.services.land_allocation_service - INFO - Allocated 1296 land units to user testuser at (0, 0)
```

Verify in database:

```bash
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
  SELECT username, COUNT(lands.land_id) as land_count
  FROM lands
  JOIN users ON lands.owner_id = users.user_id
  WHERE username = 'testuser'
  GROUP BY username;
"
```

---

## Configuration Options

The admin_config table controls land allocation behavior:

| Setting | Default | Description |
|---------|---------|-------------|
| `starter_land_enabled` | `true` | Enable/disable auto land allocation |
| `starter_land_min_size` | `36` | Minimum land size (36x36) |
| `starter_land_max_size` | `1000` | Maximum land size (1000x1000) |
| `starter_land_buffer_units` | `1` | Buffer spacing between plots |
| `starter_shape_variation_enabled` | `true` | Enable rare shapes (circle/triangle/rectangle) |

---

## Troubleshooting

### Issue: "Starter land allocation is disabled"

**Cause**: No admin_config record exists or `starter_land_enabled = false`

**Solution**:
```bash
# Check if config exists
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "SELECT * FROM admin_config;"

# If empty, follow setup steps above
# If exists but disabled, enable it:
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
  UPDATE admin_config SET starter_land_enabled = true;
"
```

### Issue: "Failed to allocate starter land"

**Cause**: Database error or validation issue

**Solution**: Check backend logs for detailed error:
```bash
docker-compose logs backend --tail=50
```

### Issue: Negative coordinates error

**Cause**: Fixed in latest version

**Solution**: Make sure you're running the latest code with the fix applied

---

## Database Migrations

If starting fresh, run migrations:

```bash
docker-compose exec backend alembic upgrade head
```

If migrations fail with "already exists" errors:

```bash
# Mark migrations as applied
docker-compose exec backend alembic stamp head
```

---

## Important Notes

⚠️ **Always run admin_config setup after `docker-compose down -v`**

⚠️ **At least one user must exist before creating admin_config** (for `updated_by_id` field)

✅ **Land allocation happens automatically during user registration**

✅ **Each user gets a random sized plot (36x36 to 1000x1000)**

✅ **Plots are placed adjacent to existing lands (never isolated)**

---

## Production Setup

For production deployments:

1. **Initialize admin_config during deployment**:
   ```bash
   kubectl exec -it backend-pod -- python init_admin_config.py
   ```

2. **Monitor allocation performance**:
   ```bash
   docker-compose logs backend | grep "Allocated.*land units"
   ```

3. **Adjust settings via Admin Dashboard**:
   - Navigate to `/admin/config`
   - Modify land allocation settings
   - Save changes

---

## Additional Resources

- [LAND_ALLOCATION_SYSTEM.md](LAND_ALLOCATION_SYSTEM.md) - Complete technical documentation
- [LAND_ALLOCATION_TEST_RESULTS.md](LAND_ALLOCATION_TEST_RESULTS.md) - Test verification results

---

**Last Updated**: 2025-11-04
