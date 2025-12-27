"""
Virtual Land World - FastAPI Main Application
Entry point for the backend API server
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
# from starlette.middleware.gzip import GZIPMiddleware  # Temporarily disabled due to API change
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db.session import init_db, close_db
from app.services.cache_service import cache_service
from app.services.biome_market_worker import biome_market_worker
from app.services.biome_market_service import biome_market_service
from app.db.session import AsyncSessionLocal
from app.models.admin_config import AdminConfig
from app.services.ip_access_service import ip_access_service
from app.services.rate_limit_service import rate_limit_service

# Setup logging (only if not already configured)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


_rate_limit_cache = {"expires": datetime.min, "value": None}


async def _get_api_rate_limit_per_minute() -> int:
    """Fetch api_requests_per_minute from AdminConfig with short-lived caching."""
    now = datetime.utcnow()
    cached_value = _rate_limit_cache["value"]
    if cached_value is not None and now < _rate_limit_cache["expires"]:
        return cached_value

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminConfig))
        config = result.scalar_one_or_none()
        limit = getattr(config, "api_requests_per_minute", None) if config else None

    _rate_limit_cache["value"] = limit
    _rate_limit_cache["expires"] = now + timedelta(seconds=30)
    return limit


def _rate_limit_identifier(request: Request) -> str:
    """Identify requester using header override, else client IP."""
    return (
        request.headers.get("X-User-Id")
        or request.headers.get("X-User-ID")
        or (request.client.host if request.client else "anonymous")
    )
    

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Startup:
    - Initialize database
    - Connect to Redis
    - Initialize biome markets
    - Start biome market worker
    - Log configuration

    Shutdown:
    - Close database connections
    - Disconnect from Redis
    - Stop biome market worker
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    try:
        await cache_service.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise

    # Initialize biome markets
    try:
        async with AsyncSessionLocal() as db:
            await biome_market_service.initialize_markets(db)
        logger.info("Biome markets initialized")
    except Exception as e:
        logger.error(f"Biome market initialization failed: {e}")
        # Not raising - markets can be created on first request

    # Start biome market worker
    try:
        biome_market_worker.start()
        logger.info("Biome market worker started")
    except Exception as e:
        logger.error(f"Biome market worker failed to start: {e}")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await biome_market_worker.stop()
    await close_db()
    await cache_service.disconnect()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Virtual Land World - Persistent 2D Virtual World with Land Ownership",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=getattr(settings, "cors_origin_regex", None),
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)


# Gzip Compression Middleware - Temporarily disabled
# app.add_middleware(
#     GZIPMiddleware,
#     minimum_size=1000
# )


# IP access control middleware (stub with cache-backed checks)
@app.middleware("http")
async def ip_access_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"

    try:
        if await ip_access_service.is_blocked(client_ip):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access from this IP is blocked"}
            )
    except Exception as exc:
        logger.error(f"IP access middleware error for {client_ip}: {exc}")

    return await call_next(request)


@app.middleware("http")
async def api_rate_limit_middleware(request: Request, call_next):
    """Global API rate limiting using per-minute bucket."""
    path = request.url.path
    if path in {"/health", "/api/health", "/api/openapi.json"} or path.startswith("/api/docs"):
        return await call_next(request)

    limit = await _get_api_rate_limit_per_minute()
    if limit is None or limit <= 0:
        return await call_next(request)

    identifier = _rate_limit_identifier(request)
    result = await rate_limit_service.check(
        bucket="api_requests_per_minute",
        identifier=identifier,
        limit=limit,
        window_seconds=60,
    )

    if result and not result.allowed:
        retry_after = max(result.reset_epoch - int(time.time()), 0)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch),
            },
        )

    response = await call_next(request)

    if result:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_epoch)

    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")

    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"- Status: {response.status_code} - Duration: {duration:.3f}s"
    )

    # Add custom headers
    response.headers["X-Process-Time"] = str(duration)

    return response


# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed error messages."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(f"Validation error on {request.url.path}: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "One or more fields failed validation",
                "details": errors
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for load balancers.

    Returns:
        dict: Health status and version info
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment
    }


@app.get("/api/v1/health", tags=["health"], include_in_schema=False)
async def health_check_api_v1():
    return await health_check()


@app.get("/health/db", tags=["health"])
async def database_health():
    """
    Database health check.

    Returns:
        dict: Database connection status
    """
    from app.db.session import check_db_connection

    is_healthy = await check_db_connection()

    if is_healthy:
        return {"status": "healthy", "database": "connected"}
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"}
        )


@app.get("/health/cache", tags=["health"])
async def cache_health():
    """
    Cache (Redis) health check.

    Returns:
        dict: Cache connection status
    """
    try:
        if cache_service.client:
            await cache_service.client.ping()
            return {"status": "healthy", "cache": "connected"}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "cache": "disconnected"}
            )
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "cache": "error"}
        )


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        dict: API welcome message and documentation links
    """
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/api/docs",
        "health": "/health"
    }


# Static files for uploads
from fastapi.staticfiles import StaticFiles
from pathlib import Path

uploads_path = Path("backend/uploads")
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


# Import and include API routers
from app.api.v1.router import api_router
app.include_router(api_router, prefix=settings.api_prefix)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
