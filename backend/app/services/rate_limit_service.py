"""
Rate limiting service backed by Redis (via cache_service.client).
Uses fixed window counters per bucket/user.
"""

import time
import logging
from typing import Optional, Tuple

from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class RateLimitResult:
    def __init__(self, allowed: bool, remaining: int, reset_epoch: int, limit: int):
        self.allowed = allowed
        self.remaining = remaining
        self.reset_epoch = reset_epoch
        self.limit = limit


class RateLimitService:
    async def check(self, bucket: str, identifier: str, limit: int, window_seconds: int) -> Optional[RateLimitResult]:
        """
        Increment and evaluate a fixed-window counter.

        Returns None if Redis is unavailable (fail-open).
        """
        if limit is None or limit <= 0:
            return None

        client = cache_service.client
        if client is None:
            return None

        now = int(time.time())
        window_start = now - (now % window_seconds)
        key = f"rl:{bucket}:{identifier}:{window_start}"

        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_seconds)

            allowed = count <= limit
            remaining = max(limit - count, 0)
            reset_epoch = window_start + window_seconds
            return RateLimitResult(allowed, remaining, reset_epoch, limit)
        except Exception as exc:
            logger.error("Rate limit check failed for %s/%s: %s", bucket, identifier, exc)
            return None


rate_limit_service = RateLimitService()
