from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from graphlane.api.events import TurnEvent
from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec
from graphlane.revision.models import ActiveRevision, RevisionSnapshot


class GraphCompiler(Protocol):
    async def compile(self, spec: AppSpec) -> Any: ...


class RevisionStore(Protocol):
    async def save_snapshot(self, snapshot: RevisionSnapshot) -> None: ...

    async def get_snapshot(
        self, app_id: str, revision: int
    ) -> RevisionSnapshot | None: ...

    async def set_active_revision(self, app_id: str, revision: int) -> None: ...

    async def get_active_revision(self, app_id: str) -> ActiveRevision | None: ...


class CheckpointStore(Protocol):
    async def load(self, thread_id: str) -> Any: ...

    async def save(self, thread_id: str, state: Any) -> None: ...


class EventBus(Protocol):
    async def publish(self, turn_id: str, event: TurnEvent) -> None: ...

    async def subscribe(self, turn_id: str) -> AsyncIterator[TurnEvent]: ...


class LockManager(Protocol):
    async def acquire(self, key: str) -> bool: ...

    async def release(self, key: str) -> None: ...


class Limiter(Protocol):
    async def try_acquire(self) -> bool: ...

    async def release(self) -> None: ...


class ToolExecutor(Protocol):
    async def build_tools(self, spec: AppSpec) -> list[Any]: ...


class PatternRegistry(Protocol):
    async def resolve(self, spec: AppSpec) -> Any: ...


class SideEffectRecorder(Protocol):
    async def record(
        self, task_type: str, payload: dict[str, Any], traceparent: str | None = None
    ) -> None: ...

