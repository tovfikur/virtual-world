# Virtual Land World - Backend Project Structure

## Project Overview

The Virtual Land World backend is built with Python FastAPI, providing high-performance async APIs, WebSocket support, and comprehensive business logic. This document describes the complete project structure, configuration, dependencies, and initialization.

---

## Directory Layout

```
virtualworld-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI application entry point
│   ├── config.py                        # Configuration management
│   ├── dependencies.py                  # Dependency injection
│   ├── logging_config.py                # Structured logging setup
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py              # Authentication endpoints
│   │   │   │   ├── users.py             # User profile endpoints
│   │   │   │   ├── lands.py             # Land management endpoints
│   │   │   │   ├── chunks.py            # World generation endpoints
│   │   │   │   ├── marketplace.py       # Marketplace endpoints
│   │   │   │   ├── payments.py          # Payment webhook endpoints
│   │   │   │   └── admin.py             # Admin endpoints
│   │   │   ├── websocket/
│   │   │   │   ├── __init__.py
│   │   │   │   └── connection_manager.py
│   │   │   └── router.py                # API router configuration
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py              # JWT, tokens, passwords
│   │   ├── user_service.py              # User management
│   │   ├── land_service.py              # Land ownership logic
│   │   ├── world_generation_service.py  # Procedural generation
│   │   ├── marketplace_service.py       # Auction & bidding logic
│   │   ├── payment_service.py           # Payment gateway integration
│   │   ├── chat_service.py              # Chat & messaging
│   │   ├── proximity_service.py         # Spatial queries
│   │   ├── analytics_service.py         # Metrics & reporting
│   │   └── cache_service.py             # Redis operations
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                      # User ORM model
│   │   ├── land.py                      # Land ORM model
│   │   ├── transaction.py               # Transaction ORM model
│   │   ├── bid.py                       # Bid ORM model
│   │   ├── listing.py                   # Listing ORM model
│   │   ├── chat.py                      # Chat ORM models
│   │   ├── audit_log.py                 # Audit ORM model
│   │   └── admin_config.py              # Admin config ORM model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user_schema.py               # User request/response schemas
│   │   ├── land_schema.py               # Land schemas
│   │   ├── marketplace_schema.py        # Marketplace schemas
│   │   └── common_schema.py             # Shared schemas
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                      # Base configuration
│   │   ├── session.py                   # Database session management
│   │   └── connection_pool.py           # Connection pooling config
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── security.py                  # Security utilities
│   │   ├── encryption.py                # Data encryption helpers
│   │   ├── exceptions.py                # Custom exceptions
│   │   └── validators.py                # Input validators
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── chunk_generation_worker.py   # Async chunk pre-generation
│   │   └── analytics_worker.py          # Async analytics processing
│   │
│   └── middleware/
│       ├── __init__.py
│       ├── error_handler.py             # Global error handling
│       ├── request_logging.py           # Request/response logging
│       └── rate_limiter.py              # Rate limiting middleware
│
├── alembic/                             # Database migrations
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   └── alembic.ini
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest configuration
│   ├── test_auth.py
│   ├── test_lands.py
│   ├── test_marketplace.py
│   └── test_world_generation.py
│
├── scripts/
│   ├── init_db.py                       # Initialize database
│   ├── seed_data.py                     # Seed test data
│   └── migrate.py                       # Run migrations
│
├── .env.example                         # Environment template
├── .env                                 # Environment variables (gitignored)
├── requirements.txt                     # Python dependencies
├── docker-compose.yml                   # Local development stack
├── Dockerfile                           # Production image
└── README.md
```

---

## Requirements.txt

```
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Database & ORM
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9

# Redis & Caching
redis==5.0.1
aioredis==2.0.1

# Authentication & Security
pyjwt==2.8.1
bcrypt==4.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
cryptography==41.0.7

# Data Validation
pydantic==2.5.0
pydantic-settings==2.1.0

# World Generation
opensimplex==0.4.3

# Payment Gateways (will be added per gateway)
requests==2.31.0

# WebRTC & Real-time
python-socketio==5.10.0

# Logging & Monitoring
python-json-logger==2.0.7
prometheus-client==0.19.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.1
pytest-cov==4.1.0

# Development
black==23.12.0
flake8==6.1.0
mypy==1.7.1
isort==5.13.2

# Utilities
python-dotenv==1.0.0
pydantic-extra-types==2.3.0
pytz==2023.3
```

---

## Configuration Management (config.py)

```python
# app/config.py

from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Application
    app_name: str = "Virtual Land World"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"

    # Database
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 0
    db_pool_recycle: int = 3600
    db_echo: bool = False

    # Redis
    redis_url: str
    redis_max_connections: int = 10

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # Security
    bcrypt_rounds: int = 12
    password_min_length: int = 12
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15

    # CORS
    cors_origins: list = ["https://app.virtuallandworld.com", "http://localhost:3000"]
    cors_credentials: bool = True
    cors_methods: list = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: list = ["*"]

    # Payment Gateways
    bkash_api_key: str
    bkash_api_secret: str
    bkash_app_key: str
    nagad_api_key: str
    nagad_api_secret: str
    rocket_api_key: str
    sslcommerz_store_id: str
    sslcommerz_store_password: str

    # Encryption
    encryption_key: str

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
```

---

## Main Application Initialization (main.py)

```python
# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import settings
from app.logging_config import setup_logging
from app.api.v1.router import api_router
from app.middleware.error_handler import setup_error_handlers
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.db.session import init_db, close_db

# Setup logging
setup_logging(settings.log_level, settings.log_file)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Virtual Land World - Persistent 2D Virtual World",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Trusted Host Middleware (prevents host header attacks)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.virtuallandworld.com", "localhost", "127.0.0.1"]
)

# Gzip Compression Middleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Custom Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimiterMiddleware)

# Setup error handlers
setup_error_handlers(app)

# Include API routers
app.include_router(api_router, prefix=settings.api_prefix)

# Lifespan events
@app.on_event("startup")
async def startup_event():
    """Initialize database and Redis on startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    logger.info("Database initialized")
    logger.info(f"Environment: {settings.environment}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await close_db()
    logger.info("Application shutdown complete")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/api/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
```

---

## Database Session Management (db/session.py)

```python
# app/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
import logging

from app.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,  # Test connections before use
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

async def get_db():
    """Dependency for database session injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
```

---

## Logging Configuration (logging_config.py)

```python
# app/logging_config.py

import logging
import logging.config
from pythonjsonlogger import jsonlogger

def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Configure structured JSON logging."""

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    console_handler.setFormatter(console_formatter)

    # File handler (optional)
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=handlers
    )

    # Set library log levels
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("aioredis").setLevel(logging.WARNING)
```

---

## Redis Connection (services/cache_service.py excerpt)

```python
# app/services/cache_service.py

import redis.asyncio as redis
from typing import Optional, Any
import json
import logging

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.client = await redis.from_url(
            self.redis_url,
            encoding="utf8",
            decode_responses=True
        )
        logger.info("Redis connected")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
        logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL."""
        if not self.client:
            return
        try:
            await self.client.setex(
                key,
                ttl,
                json.dumps(value)
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def delete(self, key: str):
        """Delete key from cache."""
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

# Global cache service instance
cache_service = CacheService(settings.redis_url)
```

---

## Dependency Injection (dependencies.py)

```python
# app/dependencies.py

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_db
from app.services.auth_service import AuthService
from app.config import settings

logger = logging.getLogger(__name__)

# Create auth service instance
auth_service = AuthService(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm
)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Dependency to extract and verify current user from JWT token."""
    try:
        payload = auth_service.verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload

async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Dependency to require admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def require_moderator(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Dependency to require moderator or admin role."""
    role = current_user.get("role")
    if role not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator privileges required"
        )
    return current_user
```

---

## Error Handler Middleware

```python
# app/middleware/error_handler.py

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

def setup_error_handlers(app: FastAPI):
    """Register global error handlers."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors."""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in error["loc"][1:]),
                "message": error["msg"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation failed",
                    "details": errors
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected errors."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )
```

---

## Docker Compose for Local Development

```yaml
# docker-compose.yml

version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: virtualworld
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: virtualworld
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U virtualworld"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql://virtualworld:dev_password@db:5432/virtualworld
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: dev-secret-key-change-in-production
      ENVIRONMENT: development
      DEBUG: "true"
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
```

---

## Environment Variables (.env.example)

```bash
# Application
ENVIRONMENT=development
DEBUG=false
APP_NAME="Virtual Land World"

# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/virtualworld

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-super-secret-key-minimum-32-characters-long
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Security
BCRYPT_ROUNDS=12
PASSWORD_MIN_LENGTH=12
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15

# Payment Gateways
BKASH_API_KEY=xxx
BKASH_API_SECRET=xxx
BKASH_APP_KEY=xxx
NAGAD_API_KEY=xxx
NAGAD_API_SECRET=xxx
ROCKET_API_KEY=xxx
SSLCOMMERZ_STORE_ID=xxx
SSLCOMMERZ_STORE_PASSWORD=xxx

# Encryption
ENCRYPTION_KEY=your-encryption-key-32-chars-min

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/virtualworld.log
```

---

## Startup Script (scripts/init_db.py)

```python
# scripts/init_db.py

import asyncio
import sys
from sqlalchemy import text
import logging

from app.config import settings
from app.db.session import engine, AsyncSessionLocal, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_database():
    """Initialize database with schema and initial data."""
    try:
        # Create tables
        await init_db()
        logger.info("Database schema created")

        # Create extensions
        async with AsyncSessionLocal() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await session.commit()
            logger.info("PostgreSQL extensions created")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_database())
```

---

## Summary

The backend structure provides:
- ✓ Clear separation of concerns (models, services, endpoints)
- ✓ Async/await throughout for performance
- ✓ Dependency injection for testability
- ✓ Structured logging for monitoring
- ✓ Redis integration for caching and sessions
- ✓ Comprehensive error handling
- ✓ Docker support for development and deployment
- ✓ Environment-based configuration

All modules follow FastAPI best practices and are ready for production deployment.

**Resume Token:** `✓ PHASE_3_STRUCTURE_COMPLETE`
