from __future__ import annotations

from redis.asyncio.client import Redis


class RedisLockManager:
    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "graphlane:lock",
        ttl_seconds: int = 60,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    async def acquire(self, key: str) -> bool:
        result = await self._redis.set(
            self._lock_key(key),
            "1",
            ex=self._ttl_seconds,
            nx=True,
        )
        return bool(result)

    async def release(self, key: str) -> None:
        await self._redis.delete(self._lock_key(key))

    def _lock_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

