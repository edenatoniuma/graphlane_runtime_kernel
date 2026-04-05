from __future__ import annotations

from redis.asyncio.client import Redis


class RedisLimiter:
    def __init__(
        self,
        redis_client: Redis,
        *,
        key: str = "graphlane:limiter:in_use",
        limit: int = 100,
    ) -> None:
        self._redis = redis_client
        self._key = key
        self._limit = limit

    async def try_acquire(self) -> bool:
        current = await self._redis.incr(self._key)
        if int(current) > self._limit:
            await self._redis.decr(self._key)
            return False
        return True

    async def release(self) -> None:
        current = await self._redis.decr(self._key)
        if int(current) <= 0:
            await self._redis.delete(self._key)

