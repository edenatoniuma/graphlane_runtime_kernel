from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import uuid4

from graphlane.api.events import EVENT_ASSISTANT_DELTA, EVENT_DONE, TurnEvent
from graphlane.api.requests import TurnRequest
from graphlane.api.results import TurnResult
from graphlane.api.specs import AppSpec
from graphlane.graph.registry import GraphRegistry


class DefaultRuntimeKernel:
    def __init__(self, registry: GraphRegistry) -> None:
        self._registry = registry

    async def invoke(self, request: TurnRequest) -> TurnResult:
        assistant_parts: list[str] = []
        turn_id = request.turn_id or uuid4().hex
        request.turn_id = turn_id

        async for event in self.stream(request):
            if event.type == EVENT_ASSISTANT_DELTA:
                assistant_parts.append(str(event.payload.get("content", "")))

        return TurnResult(
            turn_id=turn_id,
            session_id=request.session_id,
            assistant_content="".join(assistant_parts),
            finish_reason="stop",
        )

    async def stream(self, request: TurnRequest) -> AsyncIterator[TurnEvent]:
        if request.turn_id is None:
            request.turn_id = uuid4().hex

        graph = await self._registry.get_graph(request.app_id)
        response = await self._execute_graph(graph, request)
        if response:
            yield TurnEvent(
                type=EVENT_ASSISTANT_DELTA,
                payload={"content": response},
            )
        yield TurnEvent(type=EVENT_DONE, payload={"turn_id": request.turn_id})

    async def submit_async(self, request: TurnRequest) -> str:
        raise NotImplementedError("async submission is part of the second implementation wave")

    async def subscribe_async(self, turn_id: str) -> AsyncIterator[TurnEvent]:
        raise NotImplementedError("async subscription is part of the second implementation wave")
        yield TurnEvent(type=EVENT_DONE, payload={"turn_id": turn_id})

    async def publish_revision(self, spec: AppSpec) -> int:
        return await self._registry.publish_revision(spec)

    async def get_active_revision(self, app_id: str) -> int | None:
        return await self._registry.get_active_revision(app_id)

    async def warmup(self, app_id: str) -> None:
        await self._registry.warmup(app_id)

    async def _execute_graph(self, graph: Any, request: TurnRequest) -> str:
        if inspect.iscoroutinefunction(graph):
            result = await graph(request)
            return self._stringify_result(result)

        if callable(graph):
            result = graph(request)
            if inspect.isawaitable(result):
                result = await result
            return self._stringify_result(result)

        stream = getattr(graph, "stream", None)
        if callable(stream):
            result = stream(request)
            if inspect.isawaitable(result):
                result = await result
            return self._stringify_result(result)

        raise TypeError("compiled graph must be callable or expose a callable stream(request)")

    @staticmethod
    def _stringify_result(result: Any) -> str:
        if isinstance(result, TurnResult):
            return result.assistant_content
        if result is None:
            return ""
        return str(result)

