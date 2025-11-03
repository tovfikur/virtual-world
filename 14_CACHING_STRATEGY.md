# Virtual Land World - Caching Strategy

## Redis Key Patterns

```python
# app/utils/cache_keys.py

class CacheKeys:
    """Centralized Redis key naming convention."""

    # Sessions
    @staticmethod
    def session_key(user_id: str) -> str:
        return f"session:{user_id}"

    @staticmethod
    def refresh_token_key(user_id: str) -> str:
        return f"refresh_token:{user_id}"

    # Chunks
    @staticmethod
    def chunk_key(chunk_id: str) -> str:
        return f"chunk:{chunk_id}"

    @staticmethod
    def chunk_generation_key(chunk_x: int, chunk_y: int) -> str:
        return f"chunk_gen:{chunk_x}_{chunk_y}"

    # Lands
    @staticmethod
    def land_key(land_id: str) -> str:
        return f"land:{land_id}"

    @staticmethod
    def user_lands_key(user_id: str) -> str:
        return f"user_lands:{user_id}"

    # Marketplace
    @staticmethod
    def listing_key(listing_id: str) -> str:
        return f"listing:{listing_id}"

    @staticmethod
    def active_listings_key() -> str:
        return "listings:active"

    # Presence
    @staticmethod
    def presence_key(land_id: str) -> str:
        return f"presence:{land_id}"

    @staticmethod
    def user_presence_key(user_id: str) -> str:
        return f"user_presence:{user_id}"

    # Rate Limiting
    @staticmethod
    def rate_limit_key(user_id: str, endpoint: str) -> str:
        return f"rate_limit:{user_id}:{endpoint}"

    # Locks
    @staticmethod
    def lock_key(resource: str) -> str:
        return f"lock:{resource}"

    # Chat
    @staticmethod
    def chat_session_key(session_id: str) -> str:
        return f"chat:{session_id}"

    @staticmethod
    def chat_message_queue_key(session_id: str) -> str:
        return f"chat_queue:{session_id}"
```

## Cache TTLs

```python
# app/config.py (cache configuration)

CACHE_TTLs = {
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
```

## Cache Service Implementation

```python
# app/services/cache_service.py (expanded)

import redis.asyncio as redis
from typing import Optional, Any, Set
import json
import logging
import hashlib

logger = logging.getLogger(__name__)

class CacheService:
    """Redis caching service with monitoring."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.stats = {"hits": 0, "misses": 0}

    async def connect(self):
        """Connect to Redis."""
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf8",
                decode_responses=True,
                max_connections=10
            )
            await self.client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
        logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """Get value with hit/miss tracking."""
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                self.stats["hits"] += 1
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            self.stats["misses"] += 1
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value with TTL."""
        if not self.client:
            return
        try:
            await self.client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def delete(self, key: str):
        """Delete key."""
        if not self.client:
            return
        try:
            await self.client.delete(key)
            logger.debug(f"Cache delete: {key}")
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

    async def increment(self, key: str, amount: int = 1, ttl: int = 60) -> int:
        """Increment counter (for rate limiting)."""
        if not self.client:
            return 0
        try:
            value = await self.client.incr(key, amount)
            # Set TTL on first increment
            if value == amount:
                await self.client.expire(key, ttl)
            return value
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return 0

    async def add_to_set(self, key: str, *members: str):
        """Add members to set (for presence tracking)."""
        if not self.client:
            return
        try:
            await self.client.sadd(key, *members)
        except Exception as e:
            logger.error(f"Cache sadd error: {e}")

    async def remove_from_set(self, key: str, *members: str):
        """Remove members from set."""
        if not self.client:
            return
        try:
            await self.client.srem(key, *members)
        except Exception as e:
            logger.error(f"Cache srem error: {e}")

    async def get_set(self, key: str) -> Set[str]:
        """Get all members of set."""
        if not self.client:
            return set()
        try:
            return await self.client.smembers(key)
        except Exception as e:
            logger.error(f"Cache smembers error: {e}")
            return set()

    async def publish(self, channel: str, message: str):
        """Publish message to Pub/Sub channel."""
        if not self.client:
            return
        try:
            await self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Publish error: {e}")

    async def acquire_lock(
        self,
        key: str,
        ttl: int = 10,
        wait_timeout: int = 5
    ) -> bool:
        """Acquire distributed lock."""
        if not self.client:
            return False
        try:
            token = hashlib.sha256(str(time.time()).encode()).hexdigest()
            result = await self.client.set(
                key,
                token,
                ex=ttl,
                nx=True
            )
            return result is not None
        except Exception as e:
            logger.error(f"Lock acquire error: {e}")
            return False

    async def release_lock(self, key: str):
        """Release distributed lock."""
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Lock release error: {e}")

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        if self.client:
            info = await self.client.info("memory")
            memory = {
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "maxmemory": info.get("maxmemory"),
                "evicted_keys": info.get("evicted_keys")
            }
        else:
            memory = {}

        return {
            "cache_hits": self.stats["hits"],
            "cache_misses": self.stats["misses"],
            "hit_rate_percent": hit_rate,
            "memory": memory
        }

# Global cache service instance
cache_service = CacheService(settings.redis_url)
```

## Cache Invalidation

```python
# app/services/cache_invalidation_service.py

class CacheInvalidationService:
    """Handle cache invalidation patterns."""

    @staticmethod
    async def invalidate_land(land_id: str):
        """Invalidate land cache."""
        await cache_service.delete(f"land:{land_id}")

    @staticmethod
    async def invalidate_user_lands(user_id: str):
        """Invalidate user's land list."""
        await cache_service.delete(f"user_lands:{user_id}")

    @staticmethod
    async def invalidate_listing(listing_id: str):
        """Invalidate listing cache."""
        await cache_service.delete(f"listing:{listing_id}")
        await cache_service.delete("listings:active")

    @staticmethod
    async def invalidate_user_profile(user_id: str):
        """Invalidate user profile cache."""
        await cache_service.delete(f"user:{user_id}")

    @staticmethod
    async def invalidate_leaderboards():
        """Invalidate all leaderboards."""
        await cache_service.delete("leaderboard:richest")
        await cache_service.delete("leaderboard:most_valuable")

    @staticmethod
    async def invalidate_heatmaps():
        """Invalidate all heatmaps."""
        # Would need pattern deletion in Redis
        # Or track heatmap keys separately
        pass
```

## Rate Limiting with Redis

```python
# app/middleware/rate_limiter.py

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis."""

    async def dispatch(self, request: Request, call_next):
        # Get user ID or IP
        user_id = request.headers.get("user-id", request.client.host)

        # Build rate limit key
        endpoint = request.url.path
        key = f"rate_limit:{user_id}:{endpoint}"

        # Check rate limit
        count = await cache_service.increment(key, ttl=60)

        if count > 100:  # 100 requests per minute
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(100 - count)
        return response
```

## Presence Tracking

```python
# app/services/presence_service.py

class PresenceService:
    """Track user presence in chat/proximity."""

    async def mark_user_online(self, user_id: str, land_id: str):
        """Mark user as online in specific land."""
        # Add to presence set for land
        await cache_service.add_to_set(f"presence:{land_id}", user_id)

        # Set user's current land
        await cache_service.set(f"user_presence:{user_id}", land_id, ttl=3600)

    async def mark_user_offline(self, user_id: str, land_id: str):
        """Mark user as offline from land."""
        await cache_service.remove_from_set(f"presence:{land_id}", user_id)
        await cache_service.delete(f"user_presence:{user_id}")

    async def get_land_occupants(self, land_id: str) -> Set[str]:
        """Get all users in a land."""
        return await cache_service.get_set(f"presence:{land_id}")

    async def get_user_current_land(self, user_id: str) -> Optional[str]:
        """Get user's current land."""
        return await cache_service.get(f"user_presence:{user_id}")

# Global instance
presence_service = PresenceService()
```

## Cache-Aside Pattern Example

```python
async def get_user_profile(user_id: str, db: AsyncSession) -> dict:
    """Get user profile with cache-aside pattern."""
    cache_key = f"user:{user_id}"

    # Try cache first
    cached = await cache_service.get(cache_key)
    if cached:
        return cached

    # Cache miss, fetch from database
    user = await db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = {
        "user_id": str(user.user_id),
        "username": user.username,
        "balance_bdt": user.balance_bdt,
        "created_at": user.created_at.isoformat()
    }

    # Store in cache
    await cache_service.set(cache_key, profile, ttl=600)

    return profile
```

## Memory Management

```python
# Redis memory monitoring

async def monitor_redis_memory():
    """Monitor Redis memory usage."""
    while True:
        stats = await cache_service.get_stats()
        memory = stats["memory"]

        logger.info(f"Redis memory: {memory['used_memory_human']}")

        if memory.get("evicted_keys", 0) > 0:
            logger.warning(f"Keys evicted: {memory['evicted_keys']}")

        await asyncio.sleep(300)  # Check every 5 minutes
```

**Resume Token:** `✓ PHASE_3_CACHING_COMPLETE`
**✓ PHASE_3_COMPLETE** - All 6 Phase 3 backend specification files generated successfully.
