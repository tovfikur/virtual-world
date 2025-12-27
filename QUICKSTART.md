# Virtual Land World - Quick Start Guide

> Important: This project runs via Docker Compose. Use the Docker setup below; do not install Postgres/Redis/Python services natively for this project.

## 🚀 Getting Started

### Docker-First Setup (Required)

This is the supported way to run the stack locally.

```bash
# From the repository root
docker compose pull
docker compose build
docker compose up -d

# Check health and logs
docker compose ps
docker compose logs -f backend
```

Access services:

- Backend API: http://localhost:8000 (Swagger: http://localhost:8000/api/docs)
- Frontend UI: http://localhost/

To stop:

```bash
docker compose down
```

To clean volumes (Postgres/Redis data):

```bash
docker compose down -v
```

Optional: create a `.env` at repo root to override compose env vars (e.g., `DB_USER`, `DB_PASSWORD`, `JWT_SECRET_KEY`).

---

This guide will help you set up and run the Virtual Land World backend that has been implemented so far.

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker Desktop** (includes Docker Compose)
- **Git** (optional) - For version control

Note: Native installs of Python/PostgreSQL/Redis are not required for running this project.

---

## Installation Steps (Manual Dev-only)

The manual steps below are for development-only and are not required when using Docker. Prefer the Docker-First setup above.

### 1. Navigate to Backend Directory

```bash
cd K:\VirtualWorld\backend
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Database

```bash
# Start PostgreSQL (if not already running)
# Create database
createdb virtualworld

# Or using psql:
psql -U postgres
CREATE DATABASE virtualworld;
\q
```

### 5. Setup Redis

```bash
# Start Redis server
redis-server

# Or on Windows (if installed via MSI):
# Redis should start automatically as a service
```

### 6. Configure Environment

```bash
# Copy example environment file
copy .env.example .env

# Edit .env with your configuration
# Minimum required:
# - DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/virtualworld
# - REDIS_URL=redis://localhost:6379/0
# - JWT_SECRET_KEY=your-very-secure-secret-key-change-this-in-production
```

**Important:** Change the `JWT_SECRET_KEY` to a random 32+ character string for security!

---

## Running the Application (Manual Dev-only)

### Start the Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Testing the API

### With Docker Running

Ensure `docker compose up -d` is running. Then you can use Swagger at `http://localhost:8000/api/docs` or run the PowerShell test script from the host:

```powershell
powershell -ExecutionPolicy Bypass -File test_testing_debug_controls.ps1
```

The script targets the backend on `http://localhost:8000` exposed by the `backend` service.

---

### Option 1: Interactive API Documentation

Open your browser and navigate to:

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

You can test all endpoints directly from the browser!

### Option 2: Test Script (Manual Dev-only)

```bash
# In a new terminal (keep the server running)
cd K:\VirtualWorld\backend
python test_backend.py
```

Expected output:

```
============================================================
Virtual Land World - Backend API Test
============================================================

Testing health check...
Status: 200
Response: {'status': 'healthy', 'version': '1.0.0', ...}
✓ Health check passed

Testing user registration...
Status: 201
✓ Registration successful

Testing user login...
Status: 200
✓ Login successful
Access Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

✓ All tests passed!
```

### Option 3: Manual Testing with cURL

```bash
# Health check
curl http://localhost:8000/health

# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123!",
    "country_code": "BD"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'

# Get current user (replace TOKEN with actual token from login)
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer TOKEN"
```

---

## Available Endpoints

### Authentication (✅ Implemented)

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user profile

### Health Checks

- `GET /health` - Application health
- `GET /health/db` - Database health
- `GET /health/cache` - Redis health

### Coming Soon

- User endpoints (profile, balance, topup)
- Land endpoints (CRUD, search, transfer)
- Chunk endpoints (world generation)
- Marketplace endpoints (listings, bids)
- Admin endpoints (dashboard, config)

---

## Configuration Options

### Environment Variables

Edit `.env` file to configure:

```bash
# Application
ENVIRONMENT=development  # development, production
DEBUG=true              # Enable debug mode
LOG_LEVEL=INFO         # DEBUG, INFO, WARNING, ERROR

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/virtualworld
DB_POOL_SIZE=20        # Connection pool size

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=10

# JWT Security
JWT_SECRET_KEY=your-secret-key-change-this
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60  # 1 hour
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7     # 7 days

# Password Security
BCRYPT_ROUNDS=12       # Higher = more secure, slower
MAX_LOGIN_ATTEMPTS=5   # Account lockout threshold
LOCKOUT_DURATION_MINUTES=15

# CORS (for frontend)
CORS_ORIGINS=["http://localhost:3000","https://app.virtuallandworld.com"]
```

---

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**

1. Make sure PostgreSQL is running
2. Check DATABASE_URL in `.env`
3. Verify database exists: `psql -U postgres -l`

### Redis Connection Error

```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
```

**Solution:**

1. Make sure Redis is running
2. Check REDIS_URL in `.env`
3. Test Redis: `redis-cli ping` (should return PONG)

### Import Errors

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**

```bash
# Make sure virtual environment is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Reinstall dependencies
pip install -r requirements.txt
```

### Port Already in Use

```
Error: Address already in use
```

**Solution:**

```bash
# Use a different port
uvicorn app.main:app --reload --port 8001

# Or kill the process using port 8000
# Windows: netstat -ano | findstr :8000
# Linux: lsof -i :8000
```

---

## Development Workflow

### Making Changes

1. Edit code in `app/` directory
2. Server auto-reloads (if --reload flag is used)
3. Test changes in browser or with test script

### Adding New Endpoints

1. Create endpoint in `app/api/v1/endpoints/`
2. Add router to `app/api/v1/router.py`
3. Test in Swagger UI

### Database Changes

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Next Steps

1. ✅ Backend authentication is working
2. ⏳ Complete user and land endpoints (in progress)
3. ⏳ Implement world generation service
4. ⏳ Build frontend with PixiJS
5. ⏳ Add marketplace and payments
6. ⏳ Deploy to production

---

## Getting Help

### Resources

- **API Documentation:** http://localhost:8000/api/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/
- **Redis Docs:** https://redis.io/docs/

### Common Commands

```bash
# Start backend
uvicorn app.main:app --reload

# Run tests
python test_backend.py

# Check Python version
python --version

# List installed packages
pip list

# Format code
black app/

# Lint code
flake8 app/
```

---

## Project Status

**Current Phase:** API Development (60% complete)
**Overall Progress:** 40%

See [PROGRESS.md](PROGRESS.md) for detailed status.

---

**Happy Coding! 🚀**

For questions or issues, check the documentation or test the API at http://localhost:8000/api/docs
