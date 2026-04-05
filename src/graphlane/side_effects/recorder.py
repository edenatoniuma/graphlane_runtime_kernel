from __future__ import annotations

from graphlane.side_effects.outbox import OutboxStore
from graphlane.side_effects.tasks import SideEffectTask


class OutboxSideEffectRecorder:
    def __init__(self, store: OutboxStore) -> None:
        self._store = store

    async def record(
        self,
        task_type: str,
        payload: dict[str, object],
        traceparent: str | None = None,
    ) -> SideEffectTask:
        task = SideEffectTask(
            task_type=task_type,
            payload=dict(payload),
            traceparent=traceparent,
        )
        await self._store.add(task)
        return task

