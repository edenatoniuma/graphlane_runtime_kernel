from __future__ import annotations

from typing import AsyncIterator, Protocol

from .requests import TurnRequest
from .results import TurnResult
from .events import TurnEvent
from .specs import AppSpec


class RuntimeKernel(Protocol):
    async def invoke(self, request: TurnRequest) -> TurnResult: ...

    async def stream(self, request: TurnRequest) -> AsyncIterator[TurnEvent]: ...

    async def submit_async(self, request: TurnRequest) -> str: ...

    async def subscribe_async(self, turn_id: str) -> AsyncIterator[TurnEvent]: ...

    async def publish_revision(self, spec: AppSpec) -> int: ...

    async def get_active_revision(self, app_id: str) -> int | None: ...

    async def warmup(self, app_id: str) -> None: ...

