from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from graphlane.api.kernel import RuntimeKernel
from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec
from graphlane.concurrency import InMemoryLimiter, InMemoryLockManager
from graphlane.core.protocols import (
    CheckpointStore,
    EventBus,
    GraphCompiler,
    LockManager,
    Limiter,
    PatternRegistry,
    RevisionStore,
    ToolExecutor,
)
from graphlane.events import InMemoryEventBus
from graphlane.graph.registry import GraphRegistry
from graphlane.patterns import APP_TYPE_REACT, PatternRegistry as DefaultPatternRegistry, ReactPatternCompiler
from graphlane.revision.store import InMemoryRevisionStore
from graphlane.runtime.engine import DefaultRuntimeKernel
from graphlane.side_effects import (
    InMemoryOutboxStore,
    OutboxSideEffectRecorder,
    OutboxWorker,
    SideEffectExecutor,
    TASK_CACHE_INVALIDATE,
    TASK_GRAPH_DESTROY,
    TASK_GRAPH_PUBLISH,
)


class EchoGraphCompiler:
    def __init__(self, pattern_registry: DefaultPatternRegistry) -> None:
        self._pattern_registry = pattern_registry

    async def compile(self, spec: AppSpec) -> Any:
        return await self._pattern_registry.compile(spec)


@dataclass(slots=True)
class KernelBuilder:
    revision_store: RevisionStore | None = None
    checkpoint_store: CheckpointStore | None = None
    event_bus: EventBus | None = None
    lock_manager: LockManager | None = None
    limiter: Limiter | None = None
    tool_executor: ToolExecutor | None = None
    pattern_registry: PatternRegistry | None = None
    compiler: GraphCompiler | None = None
    side_effect_recorder: Any | None = None
    side_effect_executor: SideEffectExecutor | None = None
    outbox_store: Any | None = None
    outbox_worker: OutboxWorker | None = None
    auto_process_side_effects: bool = True

    def with_revision_store(self, store: RevisionStore) -> Self:
        self.revision_store = store
        return self

    def with_checkpoint_store(self, store: CheckpointStore) -> Self:
        self.checkpoint_store = store
        return self

    def with_event_bus(self, bus: EventBus) -> Self:
        self.event_bus = bus
        return self

    def with_lock_manager(self, manager: LockManager) -> Self:
        self.lock_manager = manager
        return self

    def with_limiter(self, limiter: Limiter) -> Self:
        self.limiter = limiter
        return self

    def with_tool_executor(self, executor: ToolExecutor) -> Self:
        self.tool_executor = executor
        return self

    def with_pattern_registry(self, registry: PatternRegistry) -> Self:
        self.pattern_registry = registry
        return self

    def with_compiler(self, compiler: GraphCompiler) -> Self:
        self.compiler = compiler
        return self

    def with_side_effect_recorder(self, recorder: Any) -> Self:
        self.side_effect_recorder = recorder
        return self

    def with_side_effect_executor(self, executor: SideEffectExecutor) -> Self:
        self.side_effect_executor = executor
        return self

    def with_outbox_store(self, store: Any) -> Self:
        self.outbox_store = store
        return self

    def with_outbox_worker(self, worker: OutboxWorker) -> Self:
        self.outbox_worker = worker
        return self

    def with_auto_process_side_effects(self, enabled: bool) -> Self:
        self.auto_process_side_effects = enabled
        return self

    def build(self) -> RuntimeKernel:
        revision_store = self.revision_store or InMemoryRevisionStore()
        event_bus = self.event_bus or InMemoryEventBus()
        lock_manager = self.lock_manager or InMemoryLockManager()
        limiter = self.limiter or InMemoryLimiter()
        pattern_registry = self.pattern_registry or DefaultPatternRegistry()
        pattern_registry.register(APP_TYPE_REACT, ReactPatternCompiler())
        compiler = self.compiler or EchoGraphCompiler(pattern_registry)
        registry = GraphRegistry(revision_store=revision_store, compiler=compiler)
        outbox_store = self.outbox_store or InMemoryOutboxStore()
        side_effect_executor = self.side_effect_executor or SideEffectExecutor()
        side_effect_executor.register(
            TASK_GRAPH_PUBLISH,
            lambda task: registry.activate_revision(
                str(task.payload["app_id"]),
                int(task.payload["revision"]),
            ),
        )
        side_effect_executor.register(
            TASK_GRAPH_DESTROY,
            lambda task: registry.destroy_app(str(task.payload["app_id"])),
        )
        side_effect_executor.register(TASK_CACHE_INVALIDATE, lambda task: None)
        side_effect_recorder = (
            self.side_effect_recorder or OutboxSideEffectRecorder(outbox_store)
        )
        outbox_worker = self.outbox_worker or OutboxWorker(
            store=outbox_store,
            executor=side_effect_executor,
        )
        return DefaultRuntimeKernel(
            registry=registry,
            event_bus=event_bus,
            lock_manager=lock_manager,
            limiter=limiter,
            side_effect_recorder=side_effect_recorder,
            outbox_worker=outbox_worker,
            auto_process_side_effects=self.auto_process_side_effects,
        )
