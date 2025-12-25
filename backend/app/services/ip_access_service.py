"""
IP access control service with cached lookups for blacklist and whitelist entries.
"""

from datetime import datetime, timedelta
import ipaddress
import logging
from typing import Set

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.ip_access_control import IPBlacklist, IPWhitelist

logger = logging.getLogger(__name__)


class IPAccessService:
    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._blacklist: Set[str] = set()
        self._whitelist: Set[str] = set()
        self._cache_expires_at = datetime.min

    @staticmethod
    def normalize_ip(ip: str) -> str:
        return str(ipaddress.ip_address(ip.strip()))

    async def _refresh_cache_if_needed(self):
        now = datetime.utcnow()
        if now < self._cache_expires_at:
            return

        async with AsyncSessionLocal() as db:
            # Blacklist entries that are not expired
            result = await db.execute(
                select(IPBlacklist.ip).where(
                    (IPBlacklist.expires_at.is_(None)) | (IPBlacklist.expires_at > now)
                )
            )
            self._blacklist = {row[0] for row in result.all()}

            # Whitelist entries that are not expired
            result = await db.execute(
                select(IPWhitelist.ip).where(
                    (IPWhitelist.expires_at.is_(None)) | (IPWhitelist.expires_at > now)
                )
            )
            self._whitelist = {row[0] for row in result.all()}

        self._cache_expires_at = now + self.cache_ttl
        logger.debug(
            "IP access cache refreshed: %s blacklisted, %s whitelisted",
            len(self._blacklist),
            len(self._whitelist)
        )

    async def is_blocked(self, ip: str) -> bool:
        try:
            normalized_ip = self.normalize_ip(ip)
        except ValueError:
            # If IP cannot be parsed, do not block by default
            logger.debug("Skipping IP access check for unparsable IP: %s", ip)
            return False

        await self._refresh_cache_if_needed()

        if normalized_ip in self._whitelist:
            return False
        if normalized_ip in self._blacklist:
            return True
        return False

    def invalidate_cache(self):
        self._cache_expires_at = datetime.min

    def snapshot(self):
        return {
            "blacklist": sorted(self._blacklist),
            "whitelist": sorted(self._whitelist)
        }


ip_access_service = IPAccessService()
