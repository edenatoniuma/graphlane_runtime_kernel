from __future__ import annotations

from typing import Protocol

from graphlane.side_effects.tasks import (
    STATUS_PENDING,
    SideEffectTask,
    utc_now,
)


class OutboxStore(Protocol):
    async def add(self, task: SideEffectTask) -> None: ...

    async def claim_available(self, worker_id: str, limit: int = 10) -> list[SideEffectTask]: ...

    async def mark_done(self, task: SideEffectTask) -> None: ...

    async def mark_retry(self, task: SideEffectTask, error_message: str, delay_seconds: float) -> None: ...

    async def mark_dead(self, task: SideEffectTask, error_message: str) -> None: ...


class InMemoryOutboxStore:
    def __init__(self) -> None:
        self._tasks: dict[str, SideEffectTask] = {}

    async def add(self, task: SideEffectTask) -> None:
        self._tasks[task.id] = task

    async def claim_available(self, worker_id: str, limit: int = 10) -> list[SideEffectTask]:
        now = utc_now()
        claimed: list[SideEffectTask] = []
        for task in self._tasks.values():
            if len(claimed) >= limit:
                break
            if task.status != STATUS_PENDING:
                continue
            if task.next_run_at > now:
                continue
            task.mark_running(worker_id)
            claimed.append(task)
        return claimed

    async def mark_done(self, task: SideEffectTask) -> None:
        task.mark_done()

    async def mark_retry(
        self, task: SideEffectTask, error_message: str, delay_seconds: float
    ) -> None:
        task.mark_retry(error_message=error_message, delay_seconds=delay_seconds)

    async def mark_dead(self, task: SideEffectTask, error_message: str) -> None:
        task.mark_dead(error_message=error_message)

    async def get_task(self, task_id: str) -> SideEffectTask | None:
        return self._tasks.get(task_id)

