"""
Redis client with graceful fallback to in-memory dict.

Usage:
    from app.core.redis_client import cache

    await cache.set("key", {"data": 1}, ttl=300)
    val = await cache.get("key")
    await cache.delete("key")
    await cache.incr("counter")

When REDIS_URL is set, uses real Redis. Otherwise falls back to a
process-local dict (fine for single-instance, loses state on restart).
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class _InMemoryBackend:
    """Dict-based fallback when Redis is unavailable."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = json.dumps(value) if not isinstance(value, (str, int, float)) else value
        if ttl:
            self._expiry[key] = time.time() + ttl

    async def get(self, key: str) -> Any:
        if key in self._expiry and time.time() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return None
        raw = self._store.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        return raw

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    async def incr(self, key: str) -> int:
        val = self._store.get(key, 0)
        if isinstance(val, str):
            val = int(val)
        val += 1
        self._store[key] = val
        return val

    async def expire(self, key: str, ttl: int) -> None:
        if key in self._store:
            self._expiry[key] = time.time() + ttl

    async def exists(self, key: str) -> bool:
        if key in self._expiry and time.time() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return key in self._store

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        await self.set(key, value, ttl=ttl)

    async def ping(self) -> bool:
        return True

    @property
    def is_real_redis(self) -> bool:
        return False


class _RedisBackend:
    """Async Redis wrapper using redis-py."""

    def __init__(self, url: str):
        self._url = url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        return self._client

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        r = await self._get_client()
        serialized = json.dumps(value) if not isinstance(value, (str, int, float)) else value
        if ttl:
            await r.setex(key, ttl, serialized)
        else:
            await r.set(key, serialized)

    async def get(self, key: str) -> Any:
        r = await self._get_client()
        raw = await r.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def delete(self, key: str) -> None:
        r = await self._get_client()
        await r.delete(key)

    async def incr(self, key: str) -> int:
        r = await self._get_client()
        return await r.incr(key)

    async def expire(self, key: str, ttl: int) -> None:
        r = await self._get_client()
        await r.expire(key, ttl)

    async def exists(self, key: str) -> bool:
        r = await self._get_client()
        return bool(await r.exists(key))

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        await self.set(key, value, ttl=ttl)

    async def ping(self) -> bool:
        try:
            r = await self._get_client()
            return await r.ping()
        except Exception:
            return False

    @property
    def is_real_redis(self) -> bool:
        return True


def _create_cache():
    """Create the appropriate backend based on REDIS_URL env var."""
    from app.core.config import settings

    url = settings.REDIS_URL
    if url:
        logger.info("[REDIS] Using Redis backend: %s", url[:30] + "...")
        return _RedisBackend(url)
    else:
        logger.warning("[REDIS] No REDIS_URL set — using in-memory fallback (state lost on restart)")
        return _InMemoryBackend()


# Singleton — import this everywhere
cache = _create_cache()
