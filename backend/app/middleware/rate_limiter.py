"""
Rate limiting middleware using token bucket algorithm.
Supports per-user, per-IP, and per-endpoint limits with configurable thresholds.
"""

from typing import Dict, Tuple, Optional, Callable
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
import logging
import asyncio
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float
    refill_rate: float  # Tokens per second
    tokens: float
    last_refill: datetime
    
    def add_tokens(self) -> None:
        """Add tokens based on time elapsed."""
        now = datetime.utcnow()
        time_elapsed = (now - self.last_refill).total_seconds()
        new_tokens = time_elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self.add_tokens()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def get_retry_after(self) -> int:
        """Get seconds to wait before retry."""
        self.add_tokens()
        
        if self.tokens >= 1:
            return 0
        
        # Time needed to get 1 token
        tokens_needed = 1 - self.tokens
        seconds_needed = tokens_needed / self.refill_rate
        return int(seconds_needed) + 1


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests_per_second: float
    burst_size: int
    
    def create_bucket(self) -> TokenBucket:
        """Create a token bucket for this limit."""
        return TokenBucket(
            capacity=self.burst_size,
            refill_rate=self.requests_per_second,
            tokens=self.burst_size,
            last_refill=datetime.utcnow()
        )


class RateLimiter:
    """
    Rate limiter with token bucket algorithm.
    
    Features:
    - Per-user limits
    - Per-IP limits
    - Per-endpoint limits
    - Burst allowance
    - Configurable thresholds
    - Dead man's switch (cleanup old buckets)
    """
    
    # Default limits
    DEFAULT_USER_LIMIT = RateLimit(requests_per_second=10, burst_size=50)
    DEFAULT_IP_LIMIT = RateLimit(requests_per_second=100, burst_size=200)
    DEFAULT_ENDPOINT_LIMIT = RateLimit(requests_per_second=1000, burst_size=2000)
    
    # Premium/broker limits (higher)
    PREMIUM_USER_LIMIT = RateLimit(requests_per_second=50, burst_size=250)
    BROKER_LIMIT = RateLimit(requests_per_second=500, burst_size=1000)
    
    def __init__(self):
        """Initialize rate limiter."""
        # Buckets: {key: TokenBucket}
        self.user_buckets: Dict[int, TokenBucket] = {}
        self.ip_buckets: Dict[str, TokenBucket] = {}
        self.endpoint_buckets: Dict[str, TokenBucket] = {}
        
        # Custom limits per endpoint
        self.endpoint_limits: Dict[str, RateLimit] = {}
        
        # User tiers for enhanced limits
        self.user_tiers: Dict[int, str] = {}  # {user_id: tier}
        
        logger.info("RateLimiter initialized")
    
    def set_user_tier(self, user_id: int, tier: str) -> None:
        """Set user tier for rate limiting."""
        self.user_tiers[user_id] = tier
    
    def set_endpoint_limit(self, endpoint: str, limit: RateLimit) -> None:
        """Set custom limit for an endpoint."""
        self.endpoint_limits[endpoint] = limit
    
    async def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limits.
        
        Args:
            request: HTTP request
            user_id: User ID (if authenticated)
        
        Returns:
            (allowed, retry_after_seconds)
        """
        # Check endpoint limit
        endpoint = f"{request.method} {request.url.path}"
        endpoint_allowed, retry = await self._check_endpoint_limit(endpoint)
        if not endpoint_allowed:
            return False, retry
        
        # Check IP limit
        client_ip = self._get_client_ip(request)
        ip_allowed, retry = await self._check_ip_limit(client_ip)
        if not ip_allowed:
            return False, retry
        
        # Check user limit (if authenticated)
        if user_id:
            user_allowed, retry = await self._check_user_limit(user_id)
            if not user_allowed:
                return False, retry
        
        return True, None
    
    async def _check_user_limit(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """Check per-user rate limit."""
        # Get user tier
        tier = self.user_tiers.get(user_id, "standard")
        
        # Select limit based on tier
        if tier == "broker":
            limit = self.BROKER_LIMIT
        elif tier == "premium":
            limit = self.PREMIUM_USER_LIMIT
        else:
            limit = self.DEFAULT_USER_LIMIT
        
        # Get or create bucket
        if user_id not in self.user_buckets:
            self.user_buckets[user_id] = limit.create_bucket()
        
        bucket = self.user_buckets[user_id]
        
        # Check consumption
        if bucket.consume(1.0):
            return True, None
        
        retry_after = bucket.get_retry_after()
        return False, retry_after
    
    async def _check_ip_limit(self, client_ip: str) -> Tuple[bool, Optional[int]]:
        """Check per-IP rate limit."""
        # Get or create bucket
        if client_ip not in self.ip_buckets:
            self.ip_buckets[client_ip] = self.DEFAULT_IP_LIMIT.create_bucket()
        
        bucket = self.ip_buckets[client_ip]
        
        # Check consumption
        if bucket.consume(1.0):
            return True, None
        
        retry_after = bucket.get_retry_after()
        return False, retry_after
    
    async def _check_endpoint_limit(self, endpoint: str) -> Tuple[bool, Optional[int]]:
        """Check per-endpoint rate limit."""
        # Get custom limit or use default
        limit = self.endpoint_limits.get(endpoint, self.DEFAULT_ENDPOINT_LIMIT)
        
        # Get or create bucket
        if endpoint not in self.endpoint_buckets:
            self.endpoint_buckets[endpoint] = limit.create_bucket()
        
        bucket = self.endpoint_buckets[endpoint]
        
        # Check consumption
        if bucket.consume(1.0):
            return True, None
        
        retry_after = bucket.get_retry_after()
        return False, retry_after
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For header (for proxied requests)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Use client host
        return request.client.host if request.client else "unknown"
    
    async def cleanup(self) -> int:
        """Clean up old buckets (dead man's switch)."""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        removed = 0
        
        # Clean user buckets (keep if recently used)
        to_delete = [
            user_id for user_id, bucket in self.user_buckets.items()
            if bucket.last_refill < cutoff
        ]
        for user_id in to_delete:
            del self.user_buckets[user_id]
            removed += 1
        
        # Clean IP buckets
        to_delete = [
            ip for ip, bucket in self.ip_buckets.items()
            if bucket.last_refill < cutoff
        ]
        for ip in to_delete:
            del self.ip_buckets[ip]
            removed += 1
        
        logger.debug(f"Rate limiter cleanup: {removed} old buckets removed")
        return removed
    
    def get_stats(self) -> Dict[str, int]:
        """Get rate limiter statistics."""
        return {
            "user_buckets": len(self.user_buckets),
            "ip_buckets": len(self.ip_buckets),
            "endpoint_buckets": len(self.endpoint_buckets),
            "total_buckets": len(self.user_buckets) + len(self.ip_buckets) + len(self.endpoint_buckets)
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Middleware factory
async def rate_limit_middleware(
    request: Request,
    call_next: Callable,
    rate_limiter: RateLimiter = None,
    skip_paths: Optional[list] = None
) -> Callable:
    """
    FastAPI middleware for rate limiting.
    
    Args:
        request: HTTP request
        call_next: Next middleware/handler
        rate_limiter: RateLimiter instance
        skip_paths: Paths to skip rate limiting
    
    Returns:
        Response or rate limit error
    """
    if rate_limiter is None:
        rate_limiter = get_rate_limiter()
    
    if skip_paths is None:
        skip_paths = ["/health", "/health/db", "/health/cache"]
    
    # Skip health checks and public endpoints
    if any(request.url.path.startswith(path) for path in skip_paths):
        return await call_next(request)
    
    # Extract user ID if authenticated
    user_id = None
    try:
        # Try to get user from token (if implemented)
        # This is pseudo-code - actual implementation depends on auth system
        user_id = getattr(request.state, "user_id", None)
    except:
        pass
    
    # Check rate limits
    allowed, retry_after = await rate_limiter.check_rate_limit(request, user_id)
    
    if not allowed:
        # Return 429 Too Many Requests
        headers = {"Retry-After": str(retry_after)} if retry_after else {}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            headers=headers
        )
    
    # Continue processing
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = "10"
    response.headers["X-RateLimit-Remaining"] = str(max(0, 10 - 1))
    response.headers["X-RateLimit-Reset"] = str(int(datetime.utcnow().timestamp()) + 60)
    
    return response
