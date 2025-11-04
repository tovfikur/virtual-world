# Automatic Admin User Setup

## Overview

The system now automatically creates a default admin user and initializes admin configuration when you run `docker-compose up` for the first time or after `docker-compose down -v`.

---

## Default Admin Credentials

**Email:** `demo@example.com`
**Password:** `DemoPassword123!`

---

## How It Works

### Startup Process

When you run `docker-compose up`, the backend container automatically:

1. ✅ **Waits for PostgreSQL** to be ready
2. ✅ **Runs database migrations** (`alembic upgrade head`)
3. ✅ **Checks for admin user**:
   - If `demo@example.com` exists → skips creation
   - If not exists → creates admin user
4. ✅ **Checks for admin config**:
   - If config exists → skips creation
   - If not exists → creates default config
5. ✅ **Starts FastAPI server**

### Files Involved

1. **`backend/entrypoint.sh`** - Startup script that orchestrates initialization
2. **`backend/init_db.py`** - Python script that creates admin user and config
3. **`backend/Dockerfile`** - Updated to use entrypoint script

---

## Quick Start

### Fresh Setup (After `docker-compose down -v`)

```bash
# 1. Remove all containers and volumes
docker-compose down -v

# 2. Start services (will auto-initialize)
docker-compose up -d --build

# 3. Wait for backend to be ready (check logs)
docker-compose logs -f backend

# You should see:
# ✓ PostgreSQL is ready!
# ✓ Migrations completed successfully!
# ✓ Default admin user created successfully!
# ✓ Admin config created successfully!
# 🚀 Starting FastAPI server...

# 4. Login at http://localhost/login
# Email: demo@example.com
# Password: DemoPassword123!

# 5. Access admin panel at http://localhost/admin
```

---

## Verification

### Check if Admin User Exists

```bash
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
  SELECT username, email, role FROM users WHERE email = 'demo@example.com';
"
```

Expected output:
```
 username |       email        | role
----------+--------------------+-------
 admin    | demo@example.com   | ADMIN
```

### Check if Admin Config Exists

```bash
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c "
  SELECT starter_land_enabled, starter_land_min_size FROM admin_config;
"
```

Expected output:
```
 starter_land_enabled | starter_land_min_size
----------------------+-----------------------
 t                    |                    36
```

---

## Manual Initialization (If Needed)

If auto-initialization fails for some reason, you can run it manually:

```bash
# Option 1: Run init script directly
docker-compose exec backend python init_db.py

# Option 2: Run via bash
docker-compose exec backend bash -c "python init_db.py"
```

---

## Customizing Default Admin

If you want different credentials, edit `backend/init_db.py` before building:

```python
# Line ~35-40
admin_user = User(
    user_id=uuid.uuid4(),
    username="admin",  # Change this
    email="demo@example.com",  # Change this
    role=UserRole.ADMIN,
    verified=True,
    balance_bdt=0
)
admin_user.set_password("DemoPassword123!")  # Change this
```

Then rebuild:
```bash
docker-compose down
docker-compose up -d --build
```

---

## Troubleshooting

### Issue: Admin user not created

**Check logs:**
```bash
docker-compose logs backend | grep -i "admin\|init"
```

**Common causes:**
1. Database not ready when script ran
2. Migration errors
3. Script syntax error

**Solution:**
```bash
# Run initialization manually
docker-compose exec backend python init_db.py
```

### Issue: "User already exists" but can't login

**Reset admin password:**
```bash
docker-compose exec backend python -c "
from app.models.user import User
from app.db.session import SessionLocal
from sqlalchemy import select

db = SessionLocal()
result = db.execute(select(User).where(User.email == 'demo@example.com'))
user = result.scalar_one()
user.set_password('DemoPassword123!')
db.commit()
print('Password reset successfully!')
"
```

### Issue: Script fails with "table does not exist"

**Cause:** Migrations haven't run

**Solution:**
```bash
# Run migrations manually
docker-compose exec backend alembic upgrade head

# Then run init script
docker-compose exec backend python init_db.py
```

---

## Production Deployment

For production environments:

### Option 1: Use Environment Variables

Create a production init script that reads from environment variables:

```bash
# .env
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=YourSecurePassword123!
```

### Option 2: Create Admin via API

1. Disable auto-admin creation
2. Use a secure one-time setup endpoint
3. Create admin via authenticated request

### Option 3: Database Seeding

Use a separate database seeding process during deployment:

```bash
kubectl exec -it backend-pod -- python init_db.py
```

---

## Security Notes

⚠️ **IMPORTANT for Production:**

1. **Change default credentials immediately** after first deployment
2. **Use strong passwords** (minimum 12 characters, mixed case, numbers, symbols)
3. **Enable 2FA** for admin accounts (if implemented)
4. **Restrict admin access** by IP if possible
5. **Monitor admin activity** via audit logs
6. **Rotate passwords regularly**

### Recommended: Disable Auto-Admin in Production

Edit `entrypoint.sh` and comment out the init line:

```bash
# Initialize database with admin user and config
# python init_db.py  # Disabled for production
```

Then create admin manually via secure process.

---

## What Gets Created

### Admin User
- **Username:** admin
- **Email:** demo@example.com
- **Password:** DemoPassword123! (hashed)
- **Role:** ADMIN
- **Verified:** true
- **Balance:** 0 BDT

### Admin Config
- **World Seed:** 12345
- **Starter Land:** Enabled
- **Land Size Range:** 36x36 to 1000x1000
- **Buffer Units:** 1
- **Shape Variation:** Enabled
- **Biome Distribution:** 20% each
- **Base Land Price:** 1000 BDT
- **Transaction Fee:** 5%

---

## Files Reference

### Backend Files
- `backend/entrypoint.sh` - Startup orchestration
- `backend/init_db.py` - Admin creation script
- `backend/Dockerfile` - Container configuration
- `backend/alembic/` - Database migrations

### Documentation
- `AUTOMATIC_ADMIN_SETUP.md` - This file
- `SETUP_LAND_ALLOCATION.md` - Land allocation setup
- `LAND_ALLOCATION_SYSTEM.md` - Technical documentation

---

## Complete Fresh Start Checklist

```bash
# 1. Stop and remove everything
docker-compose down -v

# 2. Optional: Remove images to force rebuild
docker-compose down --rmi all

# 3. Start fresh
docker-compose up -d --build

# 4. Watch initialization (takes ~30-60 seconds)
docker-compose logs -f backend

# 5. Verify admin created
docker-compose exec -T postgres psql -U virtualworld -d virtualworld -c \
  "SELECT email, role FROM users WHERE role = 'ADMIN';"

# 6. Login and test
# Go to: http://localhost/login
# Use: demo@example.com / DemoPassword123!
# Access: http://localhost/admin
```

---

**Last Updated:** 2025-11-05
**Version:** 1.0.0
