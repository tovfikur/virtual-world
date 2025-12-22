# Phase 2 Section 8: Deployment & Integration Guide

## Quick Start: Register Components in main.py

Add these imports and registrations to `backend/app/main.py`:

### Step 1: Import All New Components

```python
# At the top of main.py
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Import new services
from app.services.notification_service import (
    get_notification_service,
    NotificationService
)
from app.services.metrics_service import (
    get_metrics_service,
    MetricsService
)

# Import middleware
from app.middleware.rate_limiter import (
    get_rate_limiter,
    rate_limit_middleware,
    RateLimiter
)
from app.middleware.security import (
    apply_security_hardening,
    PRODUCTION_CONFIG,
    DEVELOPMENT_CONFIG
)

# Import monitoring API
from app.api.monitoring import router as monitoring_router

# Import OpenAPI generator
from app.utils.openapi_generator import generate_openapi_docs
```

### Step 2: Configure Environment Variables

```python
# Add to settings or .env
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://exchange.example.com"
]

ALLOWED_HOSTS = [
    "localhost",
    "exchange.example.com",
    "*.example.com"
]

ENABLE_HSTS = not DEBUG
ENABLE_CORS = True
METRICS_RETENTION_SECONDS = 3600
```

### Step 3: Create Lifespan Context Manager

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Virtual World Exchange API...")

    # Initialize services
    notification_service = get_notification_service()
    metrics_service = get_metrics_service()
    rate_limiter = get_rate_limiter()

    print(f"✅ NotificationService initialized")
    print(f"✅ MetricsService initialized (retention: {metrics_service.retention_seconds}s)")
    print(f"✅ RateLimiter initialized (default: 10 req/s per user)")

    yield

    # Shutdown
    print("Shutting down...")
    notification_service.clear_dead_letters()
    metrics_service.cleanup_old_measurements()
    rate_limiter.cleanup()
    print("✅ Cleanup complete")
```

### Step 4: Create FastAPI App with Lifespan

```python
app = FastAPI(
    title="Virtual World Exchange API",
    description="Comprehensive trading exchange platform with real-time notifications, metrics, and rate limiting",
    version="1.0.0",
    lifespan=lifespan
)
```

### Step 5: Apply Security Hardening

```python
# Apply security hardening based on environment
security_config = PRODUCTION_CONFIG if not DEBUG else DEVELOPMENT_CONFIG

apply_security_hardening(
    app,
    allow_origins=security_config["allow_origins"],
    allowed_hosts=security_config["allowed_hosts"],
    enable_hsts=security_config["enable_hsts"],
    enable_cors=security_config["enable_cors"],
    csp_policy=security_config["csp_policy"]
)

print("✅ Security hardening applied")
```

### Step 6: Register Rate Limiter Middleware

```python
# Get rate limiter instance
rate_limiter = get_rate_limiter()

# Configure custom tier for admin users (optional)
rate_limiter.set_user_tier("admin_user_id", "broker")

# Configure custom endpoint limits (optional)
rate_limiter.set_endpoint_limit("/api/v1/trading/execute", {
    "requests_per_second": 50,
    "burst_size": 250
})

# Add rate limiting middleware
app.add_middleware(
    rate_limit_middleware,
    rate_limiter=rate_limiter,
    skip_paths=["/health", "/health/db", "/health/cache", "/docs", "/openapi.json"]
)

print("✅ Rate limiter middleware registered")
```

### Step 7: Register Monitoring API Router

```python
# Include monitoring endpoints
app.include_router(
    monitoring_router,
    prefix="/api/v1/monitoring",
    tags=["monitoring"]
)

print("✅ Monitoring API registered at /api/v1/monitoring")
```

### Step 8: Configure OpenAPI Documentation

```python
# Override OpenAPI schema generator
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = generate_openapi_docs(app)
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

print("✅ OpenAPI documentation configured")
```

### Step 9: Add Health Check Endpoint

```python
@app.get("/health", tags=["system"])
async def health_check():
    """System health check endpoint."""
    metrics_service = get_metrics_service()
    health = metrics_service.get_health_check()

    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)
```

### Step 10: Add Startup/Shutdown Events (if not using lifespan)

```python
@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    notification_service = get_notification_service()
    metrics_service = get_metrics_service()
    rate_limiter = get_rate_limiter()

    print("✅ Services initialized")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    notification_service = get_notification_service()
    metrics_service = get_metrics_service()
    rate_limiter = get_rate_limiter()

    notification_service.clear_dead_letters()
    metrics_service.cleanup_old_measurements()
    rate_limiter.cleanup()

    print("✅ Cleanup complete")
```

---

## Complete main.py Template

```python
"""
FastAPI application with Phase 2 Section 8 enhancements:
- Real-time notifications
- Performance monitoring
- API rate limiting
- Security hardening
- Automatic API documentation
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Import new services and middleware
from app.services.notification_service import get_notification_service
from app.services.metrics_service import get_metrics_service
from app.middleware.rate_limiter import (
    get_rate_limiter,
    rate_limit_middleware
)
from app.middleware.security import (
    apply_security_hardening,
    PRODUCTION_CONFIG,
    DEVELOPMENT_CONFIG
)
from app.api.monitoring import router as monitoring_router
from app.utils.openapi_generator import generate_openapi_docs

# Configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://exchange.example.com"
]

ALLOWED_HOSTS = [
    "localhost",
    "exchange.example.com",
    "*.example.com"
]


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Virtual World Exchange API...")

    notification_service = get_notification_service()
    metrics_service = get_metrics_service()
    rate_limiter = get_rate_limiter()

    logger.info("✅ NotificationService initialized")
    logger.info(f"✅ MetricsService initialized (retention: {metrics_service.retention_seconds}s)")
    logger.info("✅ RateLimiter initialized (10 req/s default)")

    yield

    # Shutdown
    logger.info("🛑 Shutting down...")
    notification_service.clear_dead_letters()
    metrics_service.cleanup_old_measurements()
    rate_limiter.cleanup()
    logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="Virtual World Exchange API",
    description="Comprehensive trading exchange platform",
    version="1.0.0",
    lifespan=lifespan
)

# Select security configuration
security_config = PRODUCTION_CONFIG if not DEBUG else DEVELOPMENT_CONFIG

# Apply security hardening
apply_security_hardening(
    app,
    allow_origins=security_config["allow_origins"],
    allowed_hosts=security_config["allowed_hosts"],
    enable_hsts=security_config["enable_hsts"],
    enable_cors=security_config["enable_cors"],
    csp_policy=security_config["csp_policy"]
)
logger.info("✅ Security hardening applied")

# Register rate limiter middleware
rate_limiter = get_rate_limiter()
app.add_middleware(
    rate_limit_middleware,
    rate_limiter=rate_limiter,
    skip_paths=["/health", "/health/db", "/health/cache", "/docs", "/openapi.json"]
)
logger.info("✅ Rate limiter middleware registered")

# Register monitoring API
app.include_router(
    monitoring_router,
    prefix="/api/v1/monitoring",
    tags=["monitoring"]
)
logger.info("✅ Monitoring API registered")

# Configure OpenAPI documentation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = generate_openapi_docs(app)
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
logger.info("✅ OpenAPI documentation configured")

# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check():
    """System health check endpoint."""
    metrics_service = get_metrics_service()
    health = metrics_service.get_health_check()
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)

# Root endpoint
@app.get("/", tags=["system"])
async def root():
    """API root endpoint."""
    return {
        "name": "Virtual World Exchange API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs",
        "openapi_schema": "/openapi.json"
    }

# Include other routers (existing)
# from app.api import trading, market_data, orders
# app.include_router(trading.router, prefix="/api/v1/trading")
# app.include_router(market_data.router, prefix="/api/v1/market-data")
# app.include_router(orders.router, prefix="/api/v1/orders")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="info"
    )
```

---

## Testing the Integration

### 1. Run the Application

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "checks": {
    "api_latency": "ok",
    "order_matching": "ok",
    "database": "ok"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 3. Test Rate Limiting

```bash
# Make multiple requests quickly
for i in {1..15}; do
  curl -i http://localhost:8000/health
  sleep 0.1
done
```

You should see HTTP 429 responses after exceeding 10 req/s.

### 4. Test Monitoring Endpoints

```bash
# Get API metrics
curl http://localhost:8000/api/v1/monitoring/metrics/api?period_seconds=60

# Get dashboard
curl http://localhost:8000/api/v1/monitoring/dashboard

# Get system status
curl http://localhost:8000/api/v1/monitoring/system/status
```

### 5. View API Documentation

Open browser: `http://localhost:8000/docs`

---

## Running Tests

```bash
# Run all Phase 2 Section 8 tests
pytest backend/tests/test_phase2_section8.py -v

# Run with coverage
pytest backend/tests/test_phase2_section8.py --cov=app --cov-report=html

# Run specific test class
pytest backend/tests/test_phase2_section8.py::TestNotificationService -v

# Run specific test
pytest backend/tests/test_phase2_section8.py::TestNotificationService::test_subscribe_single_type -v
```

---

## Production Deployment Checklist

### Before Deployment

- [ ] Set `DEBUG = False`
- [ ] Use `PRODUCTION_CONFIG` security settings
- [ ] Configure `ALLOWED_ORIGINS` for your domain
- [ ] Configure `ALLOWED_HOSTS` for your domain
- [ ] Set `ENABLE_HSTS = True`
- [ ] Generate SSL/TLS certificates
- [ ] Run full test suite: `pytest -v`
- [ ] Review security headers in response

### Deployment

- [ ] Deploy with gunicorn or similar WSGI server
- [ ] Use nginx as reverse proxy
- [ ] Enable HTTP/2 and compression
- [ ] Set up monitoring and alerting
- [ ] Configure backup and disaster recovery
- [ ] Document runbook and troubleshooting

### Post-Deployment

- [ ] Monitor metrics dashboard
- [ ] Check rate limit effectiveness
- [ ] Verify notification delivery
- [ ] Test security headers (securityheaders.com)
- [ ] Monitor dead letter queue size
- [ ] Set up alerting for degraded health

---

## Troubleshooting

### Rate Limiter Not Working

1. Check if middleware is registered before routes
2. Verify `skip_paths` configuration
3. Check X-RateLimit-\* headers in response

### Metrics Not Updating

1. Verify `MetricsService` initialization
2. Check that endpoints are recording latency
3. Monitor metrics aggregation with `get_dashboard_metrics()`

### Notifications Not Delivering

1. Check dead letter queue: `/api/v1/monitoring/notifications/stats`
2. Verify subscription exists
3. Check delivery callbacks are registered

### Security Headers Missing

1. Verify `apply_security_hardening()` called
2. Check middleware order (security first)
3. Verify CSP policy in `PRODUCTION_CONFIG`

---

## Performance Tuning

### For High Traffic

```python
# Increase rate limits for premium users
rate_limiter.set_user_tier("premium_user_1", "premium")

# Increase message batch timeout for better throughput
notification_service.batch_timeout = 200  # 200ms

# Increase metrics retention for longer analysis window
metrics_service.retention_seconds = 7200  # 2 hours
```

### For Low Latency

```python
# Decrease message batch size for lower latency
notification_service.batch_size = 5  # 5 messages or 50ms

# Decrease metrics retention window for faster aggregation
metrics_service.retention_seconds = 600  # 10 minutes

# Reduce cleanup interval
rate_limiter.cleanup_interval = 600  # 10 minutes
```

---

## Next Steps

1. ✅ Copy this template into your `backend/app/main.py`
2. ✅ Run the application: `python -m uvicorn app.main:app --reload`
3. ✅ Test endpoints (health, metrics, monitoring)
4. ✅ Run test suite: `pytest backend/tests/test_phase2_section8.py -v`
5. ✅ Review logs for any issues
6. ✅ Deploy to production with PRODUCTION_CONFIG

---

Generated: 2024-01-15 | Section 8: API & UI Enhancements
