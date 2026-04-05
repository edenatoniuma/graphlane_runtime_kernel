from __future__ import annotations

import asyncio


class InMemoryLimiter:
    def __init__(self, limit: int = 100) -> None:
        self._limit = limit
        self._guard = asyncio.Lock()
        self._in_use = 0

    async def try_acquire(self) -> bool:
        async with self._guard:
            if self._in_use >= self._limit:
                return False
            self._in_use += 1
            return True

    async def release(self) -> None:
        async with self._guard:
            if self._in_use > 0:
                self._in_use -= 1

