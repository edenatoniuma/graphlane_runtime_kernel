from __future__ import annotations

import asyncio
from collections.abc import Sequence

from graphlane.side_effects.executor import SideEffectExecutor
from graphlane.side_effects.outbox import OutboxStore
from graphlane.side_effects.tasks import SideEffectTask


class OutboxWorker:
    def __init__(
        self,
        store: OutboxStore,
        executor: SideEffectExecutor,
        worker_id: str = "graphlane-outbox-worker",
        retry_delays: Sequence[float] = (1.0, 2.0, 4.0),
    ) -> None:
        self._store = store
        self._executor = executor
        self._worker_id = worker_id
        self._retry_delays = tuple(retry_delays)

    async def process_once(self, limit: int = 10) -> int:
        tasks = await self._store.claim_available(worker_id=self._worker_id, limit=limit)
        processed = 0
        for task in tasks:
            processed += 1
            await self._handle_task(task)
        return processed

    async def run_forever(self, poll_interval: float = 1.0) -> None:
        while True:
            processed = await self.process_once()
            if processed == 0:
                await asyncio.sleep(poll_interval)

    async def _handle_task(self, task: SideEffectTask) -> None:
        try:
            await self._executor.execute(task)
        except Exception as exc:
            if task.retry_count >= task.max_retries:
                await self._store.mark_dead(task, error_message=str(exc))
                return
            delay = self._delay_for_retry(task.retry_count)
            await self._store.mark_retry(task, error_message=str(exc), delay_seconds=delay)
            return

        await self._store.mark_done(task)

    def _delay_for_retry(self, retry_count: int) -> float:
        if retry_count < len(self._retry_delays):
            return self._retry_delays[retry_count]
        return self._retry_delays[-1]

