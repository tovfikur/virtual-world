"""
Cache Service
Redis-based caching with async support
"""

import redis.asyncio as redis
from typing import Optional, Any, Set
import json
import logging
import hashlib
import time

from app.config import settings, CACHE_TTLS

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service with monitoring.

    Features:
    - Async Redis operations
    - Automatic JSON serialization
    - TTL management
    - Hit/miss tracking
    - Distributed locking
    - Set operations for presence tracking
    - Pub/Sub support
    """

    def __init__(self, redis_url: str):
        """
        Initialize cache service.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.stats = {"hits": 0, "misses": 0}

    async def connect(self) -> None:
        """
        Connect to Redis server.

        Raises:
            Exception: If connection fails
        """
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf8",
                decode_responses=True,
                max_connections=settings.redis_max_connections
            )
            await self.client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
        logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with hit/miss tracking.

        Args:
            key: Cache key

        Returns:
            Optional[Any]: Cached value or None if not found

        Example:
            ```python
            user = await cache_service.get("user:123")
            if user:
                # Cache hit
                pass
            ```
        """
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
            logger.error(f"Cache get error for key '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (default from CACHE_TTLS)

        Returns:
            bool: True if successful, False otherwise

        Example:
            ```python
            await cache_service.set("user:123", user_data, ttl=3600)
            ```
        """
        if not self.client:
            return False

        if ttl is None:
            ttl = CACHE_TTLS.get("session", 3600)

        try:
            await self.client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key was deleted, False otherwise
        """
        if not self.client:
            return False

        try:
            result = await self.client.delete(key)
            logger.debug(f"Cache delete: {key}")
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            return False

    async def delete_by_prefix(self, prefix: str, batch_size: int = 500) -> int:
        """
        Delete all keys matching a prefix.

        Args:
            prefix: Prefix to match (without wildcard)
            batch_size: Number of keys to scan per iteration

        Returns:
            int: Number of keys deleted
        """
        if not self.client:
            return 0

        pattern = f"{prefix}*"
        cursor = "0"
        deleted = 0

        try:
            while True:
                cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=batch_size)
                if keys:
                    deleted += await self.client.delete(*keys)
                if cursor == 0 or cursor == "0":
                    break
            logger.info(f"Cache delete_by_prefix prefix={prefix} deleted={deleted}")
            return deleted
        except Exception as e:
            logger.error(f"Cache delete_by_prefix error for prefix '{prefix}': {e}")
            return deleted

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key exists, False otherwise
        """
        if not self.client:
            return False

        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key '{key}': {e}")
            return False

    async def increment(
        self,
        key: str,
        amount: int = 1,
        ttl: int = 60
    ) -> int:
        """
        Increment counter (for rate limiting).

        Args:
            key: Cache key
            amount: Amount to increment by
            ttl: TTL for key (set on first increment)

        Returns:
            int: New counter value

        Example:
            ```python
            count = await cache_service.increment("rate_limit:user:123")
            if count > 100:
                # Rate limit exceeded
                pass
            ```
        """
        if not self.client:
            return 0

        try:
            value = await self.client.incr(key, amount)
            # Set TTL on first increment
            if value == amount:
                await self.client.expire(key, ttl)
            return value
        except Exception as e:
            logger.error(f"Cache increment error for key '{key}': {e}")
            return 0

    async def add_to_set(self, key: str, *members: str) -> bool:
        """
        Add members to set (for presence tracking).

        Args:
            key: Set key
            members: Member values to add

        Returns:
            bool: True if successful

        Example:
            ```python
            await cache_service.add_to_set("presence:land:123", "user:456")
            ```
        """
        if not self.client:
            return False

        try:
            await self.client.sadd(key, *members)
            return True
        except Exception as e:
            logger.error(f"Cache sadd error for key '{key}': {e}")
            return False

    async def remove_from_set(self, key: str, *members: str) -> bool:
        """
        Remove members from set.

        Args:
            key: Set key
            members: Member values to remove

        Returns:
            bool: True if successful
        """
        if not self.client:
            return False

        try:
            await self.client.srem(key, *members)
            return True
        except Exception as e:
            logger.error(f"Cache srem error for key '{key}': {e}")
            return False

    async def get_set(self, key: str) -> Set[str]:
        """
        Get all members of set.

        Args:
            key: Set key

        Returns:
            Set[str]: Set members

        Example:
            ```python
            users = await cache_service.get_set("presence:land:123")
            print(f"Users in land: {len(users)}")
            ```
        """
        if not self.client:
            return set()

        try:
            return await self.client.smembers(key)
        except Exception as e:
            logger.error(f"Cache smembers error for key '{key}': {e}")
            return set()

    async def publish(self, channel: str, message: str) -> bool:
        """
        Publish message to Pub/Sub channel.

        Args:
            channel: Channel name
            message: Message to publish

        Returns:
            bool: True if successful

        Example:
            ```python
            await cache_service.publish("land_updates", json.dumps(data))
            ```
        """
        if not self.client:
            return False

        try:
            await self.client.publish(channel, message)
            return True
        except Exception as e:
            logger.error(f"Publish error for channel '{channel}': {e}")
            return False

    async def acquire_lock(
        self,
        key: str,
        ttl: int = 10,
        wait_timeout: int = 5
    ) -> bool:
        """
        Acquire distributed lock.

        Args:
            key: Lock key
            ttl: Lock time-to-live in seconds
            wait_timeout: Max time to wait for lock

        Returns:
            bool: True if lock acquired, False otherwise

        Example:
            ```python
            if await cache_service.acquire_lock("lock:purchase:land:123"):
                try:
                    # Process purchase
                    pass
                finally:
                    await cache_service.release_lock("lock:purchase:land:123")
            ```
        """
        if not self.client:
            return False

        try:
            token = hashlib.sha256(str(time.time()).encode()).hexdigest()
            result = await self.client.set(
                key,
                token,
                ex=ttl,
                nx=True  # Only set if doesn't exist
            )
            return result is not None
        except Exception as e:
            logger.error(f"Lock acquire error for key '{key}': {e}")
            return False

    async def release_lock(self, key: str) -> bool:
        """
        Release distributed lock.

        Args:
            key: Lock key

        Returns:
            bool: True if released, False otherwise
        """
        return await self.delete(key)

    async def is_healthy(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            bool: True if Redis is responding, False otherwise

        Example:
            ```python
            if await cache_service.is_healthy():
                print("Redis is healthy")
            ```
        """
        if not self.client:
            return False

        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics including hit rate and memory usage

        Example:
            ```python
            stats = await cache_service.get_stats()
            print(f"Hit rate: {stats['hit_rate_percent']}%")
            ```
        """
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        memory = {}
        if self.client:
            try:
                info = await self.client.info("memory")
                memory = {
                    "used_memory": info.get("used_memory"),
                    "used_memory_human": info.get("used_memory_human"),
                    "maxmemory": info.get("maxmemory"),
                    "evicted_keys": info.get("evicted_keys")
                }
            except Exception as e:
                logger.error(f"Failed to get Redis memory info: {e}")

        return {
            "cache_hits": self.stats["hits"],
            "cache_misses": self.stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "memory": memory
        }

    async def flush_all(self) -> bool:
        """
        Flush the entire Redis database.

        Returns:
            bool: True if successful
        """
        if not self.client:
            return False

        try:
            await self.client.flushdb()
            logger.warning("Cache flushdb executed by admin")
            return True
        except Exception as e:
            logger.error(f"Cache flush_all error: {e}")
            return False


# Global cache service instance
cache_service = CacheService(settings.redis_url)
