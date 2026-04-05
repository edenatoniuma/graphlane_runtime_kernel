from __future__ import annotations

import asyncio


class InMemoryLockManager:
    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._active_keys: set[str] = set()

    async def acquire(self, key: str) -> bool:
        async with self._guard:
            if key in self._active_keys:
                return False
            self._active_keys.add(key)
            return True

    async def release(self, key: str) -> None:
        async with self._guard:
            self._active_keys.discard(key)

