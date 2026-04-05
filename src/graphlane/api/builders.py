from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from graphlane.api.kernel import RuntimeKernel
from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec
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
from graphlane.graph.registry import GraphRegistry
from graphlane.revision.store import InMemoryRevisionStore
from graphlane.runtime.engine import DefaultRuntimeKernel


class EchoGraphCompiler:
    async def compile(self, spec: AppSpec) -> Any:
        async def run(request: TurnRequest) -> str:
            prefix = spec.prompt or spec.name
            return f"{prefix}: {request.query}"

        return run


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

    def build(self) -> RuntimeKernel:
        revision_store = self.revision_store or InMemoryRevisionStore()
        compiler = self.compiler or EchoGraphCompiler()
        registry = GraphRegistry(revision_store=revision_store, compiler=compiler)
        return DefaultRuntimeKernel(registry=registry)

