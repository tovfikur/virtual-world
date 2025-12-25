"""
Configuration management using Pydantic Settings
Loads configuration from environment variables and .env file
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os
import json


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_name: str = Field(default="Virtual Land World", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")

    @validator('api_prefix')
    def fix_git_bash_path(cls, v):
        """Fix Git Bash MSYS path conversion on Windows"""
        if ':' in v and ('/' in v or '\\' in v):
            # Git Bash converted /api/v1 to C:/Program Files/Git/api/v1
            # Extract the part after the last occurrence of a Windows-style path
            parts = v.replace('\\', '/').split('/')
            if len(parts) >= 3 and parts[-2] == 'api' and parts[-1].startswith('v'):
                return f"/api/{parts[-1]}"
        return v

    # Database
    database_url: str = Field(env="DATABASE_URL")
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=0, env="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    db_echo: bool = Field(default=False, env="DB_ECHO")

    # Redis
    redis_url: str = Field(env="REDIS_URL")
    redis_max_connections: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")

    # JWT Security
    jwt_secret_key: str = Field(env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # Password Security
    bcrypt_rounds: int = Field(default=12, env="BCRYPT_ROUNDS")
    password_min_length: int = Field(default=12, env="PASSWORD_MIN_LENGTH")
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    lockout_duration_minutes: int = Field(default=15, env="LOCKOUT_DURATION_MINUTES")

    # CORS
    cors_origins: List[str] = Field(default=[], env="CORS_ORIGINS")
    cors_origin_regex: Optional[str] = Field(default=None, env="CORS_ORIGIN_REGEX")
    cors_credentials: bool = Field(default=True, env="CORS_CREDENTIALS")
    cors_methods: List[str] = Field(
        default=["*"],
        env="CORS_METHODS"
    )
    cors_headers: List[str] = Field(default=["*"], env="CORS_HEADERS")

    # Payment Gateways
    backend_url: str = Field(
        default="http://localhost:8000",
        env="BACKEND_URL"
    )

    # bKash
    bkash_api_key: str = Field(default="", env="BKASH_API_KEY")
    bkash_api_secret: str = Field(default="", env="BKASH_API_SECRET")
    bkash_app_key: str = Field(default="", env="BKASH_APP_KEY")
    bkash_app_secret: str = Field(default="", env="BKASH_APP_SECRET")
    bkash_api_url: str = Field(
        default="https://checkout.sandbox.bka.sh/v1.2.0-beta",
        env="BKASH_API_URL"
    )

    # Nagad
    nagad_api_key: str = Field(default="", env="NAGAD_API_KEY")
    nagad_api_secret: str = Field(default="", env="NAGAD_API_SECRET")
    nagad_merchant_id: str = Field(default="", env="NAGAD_MERCHANT_ID")
    nagad_merchant_key: str = Field(default="", env="NAGAD_MERCHANT_KEY")
    nagad_api_url: str = Field(
        default="http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0",
        env="NAGAD_API_URL"
    )

    # Rocket
    rocket_api_key: str = Field(default="", env="ROCKET_API_KEY")
    rocket_api_secret: str = Field(default="", env="ROCKET_API_SECRET")
    rocket_merchant_id: str = Field(default="", env="ROCKET_MERCHANT_ID")
    rocket_secret_key: str = Field(default="", env="ROCKET_SECRET_KEY")
    rocket_api_url: str = Field(
        default="https://sandbox.rocketdigital.com.bd/api",
        env="ROCKET_API_URL"
    )

    # SSLCommerz
    sslcommerz_store_id: str = Field(default="", env="SSLCOMMERZ_STORE_ID")
    sslcommerz_store_password: str = Field(default="", env="SSLCOMMERZ_STORE_PASSWORD")
    sslcommerz_api_url: str = Field(
        default="https://sandbox.sslcommerz.com",
        env="SSLCOMMERZ_API_URL"
    )

    # Encryption
    encryption_key: str = Field(env="ENCRYPTION_KEY")

    # Logging
    # Default to WARNING to avoid noisy output; can be overridden via LOG_LEVEL.
    log_level: str = Field(default="WARNING", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")

    # World Generation
    # Seed: "Topu" encoded as integer (84, 111, 112, 117 -> 1416589429)
    default_world_seed: int = Field(default=1416589429, env="DEFAULT_WORLD_SEED")
    chunk_cache_ttl: int = Field(default=3600, env="CHUNK_CACHE_TTL")
    max_chunks_in_memory: int = Field(default=1000, env="MAX_CHUNKS_IN_MEMORY")

    @property
    def WORLD_SEED(self) -> int:
        """Get world seed for terrain generation."""
        return self.default_world_seed

    # File Storage
    storage_backend: str = Field(default="local", env="STORAGE_BACKEND")
    aws_access_key_id: str = Field(default="", env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", env="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: str = Field(default="virtualworld-chunks", env="AWS_S3_BUCKET")
    aws_region: str = Field(default="ap-south-1", env="AWS_REGION")

    # Monitoring
    prometheus_enabled: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @validator("cors_methods", pre=True)
    def parse_cors_methods(cls, v):
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [method.strip() for method in v.split(",")]
        return v

    @validator("cors_headers", pre=True)
    def parse_cors_headers(cls, v):
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [header.strip() for header in v.split(",")]
        return v

    @validator("jwt_secret_key")
    def validate_jwt_secret(cls, v, values):
        """Ensure JWT secret is strong in production."""
        env = values.get("environment", "development")
        if env == "production":
            if not v or len(v) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
            if v.startswith("dev-") or "change" in v.lower() or "secret" in v.lower():
                raise ValueError("JWT_SECRET_KEY appears to be a dev/demo key; use a strong random key in production")
        return v

    @validator("encryption_key")
    def validate_encryption_key(cls, v, values):
        """Ensure encryption key is strong in production."""
        env = values.get("environment", "development")
        if env == "production":
            if not v or len(v) < 32:
                raise ValueError("ENCRYPTION_KEY must be at least 32 characters in production")
            if v.startswith("dev-") or "change" in v.lower() or "secret" in v.lower():
                raise ValueError("ENCRYPTION_KEY appears to be a dev/demo key; use a strong random key in production")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Cache TTL configurations
CACHE_TTLS = {
    "session": 3600,  # 1 hour
    "refresh_token": 7 * 24 * 60 * 60,  # 7 days
    "chunk": 3600,  # 1 hour
    "land": 300,  # 5 minutes
    "listing": 300,  # 5 minutes
    "presence": 60,  # 1 minute
    "rate_limit": 60,  # 1 minute
    "user_profile": 600,  # 10 minutes
    "analytics": 3600,  # 1 hour
    "leaderboard": 1800,  # 30 minutes
    "heatmap": 3600,  # 1 hour
}
