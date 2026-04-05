from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from graphlane.api.events import (
    EVENT_ASSISTANT_DELTA,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_TOOL_END,
    TurnEvent,
)
from graphlane.api.requests import TurnRequest
from graphlane.api.results import TurnResult
from graphlane.api.specs import AppSpec
from graphlane.core.protocols import EventBus, LockManager, Limiter
from graphlane.graph.registry import GraphRegistry
from graphlane.side_effects import TASK_GRAPH_PUBLISH


class DefaultRuntimeKernel:
    def __init__(
        self,
        registry: GraphRegistry,
        event_bus: EventBus,
        lock_manager: LockManager,
        limiter: Limiter,
        side_effect_recorder: Any,
        outbox_worker: Any | None = None,
        auto_process_side_effects: bool = True,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._lock_manager = lock_manager
        self._limiter = limiter
        self._side_effect_recorder = side_effect_recorder
        self._outbox_worker = outbox_worker
        self._auto_process_side_effects = auto_process_side_effects
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def invoke(self, request: TurnRequest) -> TurnResult:
        assistant_parts: list[str] = []
        tool_records: list[dict[str, Any]] = []
        error_message: str | None = None
        turn_id = request.turn_id or uuid4().hex
        request.turn_id = turn_id

        async for event in self.stream(request):
            if event.type == EVENT_ASSISTANT_DELTA:
                assistant_parts.append(str(event.payload.get("content", "")))
            elif event.type == EVENT_TOOL_END:
                tool_records.append(dict(event.payload))
            elif event.type == EVENT_ERROR:
                error_message = str(event.payload.get("message", ""))

        return TurnResult(
            turn_id=turn_id,
            session_id=request.session_id,
            assistant_content="".join(assistant_parts),
            finish_reason="stop",
            tool_records=tool_records,
            error_message=error_message,
        )

    async def stream(self, request: TurnRequest) -> AsyncIterator[TurnEvent]:
        if request.turn_id is None:
            request.turn_id = uuid4().hex

        graph = await self._registry.get_graph(request.app_id)
        async for event in self._stream_graph(graph, request):
            yield event
        yield TurnEvent(type=EVENT_DONE, payload={"turn_id": request.turn_id})

    async def submit_async(self, request: TurnRequest) -> str:
        turn_id = request.turn_id or uuid4().hex
        request.turn_id = turn_id

        task = asyncio.create_task(self._run_async_turn(request), name=f"graphlane-turn-{turn_id}")
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return turn_id

    async def subscribe_async(self, turn_id: str) -> AsyncIterator[TurnEvent]:
        async for event in self._event_bus.subscribe(turn_id):
            yield event

    async def publish_revision(self, spec: AppSpec) -> int:
        await self._registry.store_revision(spec)
        await self._side_effect_recorder.record(
            TASK_GRAPH_PUBLISH,
            {"app_id": spec.app_id, "revision": spec.revision},
        )
        if self._auto_process_side_effects and self._outbox_worker is not None:
            await self._outbox_worker.process_once()
        return spec.revision

    async def get_active_revision(self, app_id: str) -> int | None:
        return await self._registry.get_active_revision(app_id)

    async def warmup(self, app_id: str) -> None:
        await self._registry.warmup(app_id)

    async def _run_async_turn(self, request: TurnRequest) -> None:
        lock_acquired = await self._lock_manager.acquire(request.session_id)
        if not lock_acquired:
            await self._publish_terminal_error(
                request.turn_id,
                "session is already executing",
            )
            return

        limiter_acquired = False
        try:
            limiter_acquired = await self._limiter.try_acquire()
            if not limiter_acquired:
                await self._publish_terminal_error(
                    request.turn_id,
                    "global concurrency limit reached",
                )
                return

            async for event in self.stream(request):
                await self._event_bus.publish(request.turn_id, event)
        except Exception as exc:
            await self._publish_terminal_error(request.turn_id, str(exc))
        finally:
            if limiter_acquired:
                await self._limiter.release()
            await self._lock_manager.release(request.session_id)

    async def _publish_terminal_error(self, turn_id: str | None, message: str) -> None:
        if turn_id is None:
            turn_id = uuid4().hex
        await self._event_bus.publish(
            turn_id,
            TurnEvent(type=EVENT_ERROR, payload={"message": message}),
        )
        await self._event_bus.publish(
            turn_id,
            TurnEvent(type=EVENT_DONE, payload={"turn_id": turn_id}),
        )

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

    async def _stream_graph(self, graph: Any, request: TurnRequest) -> AsyncIterator[TurnEvent]:
        stream_events = getattr(graph, "stream_events", None)
        if callable(stream_events):
            async for event in stream_events(request):
                yield event
            return

        response = await self._execute_graph(graph, request)
        if response:
            yield TurnEvent(
                type=EVENT_ASSISTANT_DELTA,
                payload={"content": response},
            )

    @staticmethod
    def _stringify_result(result: Any) -> str:
        if isinstance(result, TurnResult):
            return result.assistant_content
        if result is None:
            return ""
        return str(result)
