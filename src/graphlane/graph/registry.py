from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from graphlane.api.specs import AppSpec
from graphlane.core.protocols import GraphCompiler, RevisionStore
from graphlane.revision.models import RevisionSnapshot


@dataclass(slots=True)
class CachedGraph:
    revision: int
    graph: Any


class GraphRegistry:
    def __init__(self, revision_store: RevisionStore, compiler: GraphCompiler) -> None:
        self._revision_store = revision_store
        self._compiler = compiler
        self._active_graphs: dict[str, CachedGraph] = {}

    async def publish_revision(self, spec: AppSpec) -> int:
        snapshot = RevisionSnapshot(app_id=spec.app_id, revision=spec.revision, spec=spec)
        await self._revision_store.save_snapshot(snapshot)
        await self._revision_store.set_active_revision(spec.app_id, spec.revision)
        self._active_graphs.pop(spec.app_id, None)
        return spec.revision

    async def get_active_revision(self, app_id: str) -> int | None:
        active = await self._revision_store.get_active_revision(app_id)
        return None if active is None else active.revision

    async def get_graph(self, app_id: str) -> Any:
        active = await self._revision_store.get_active_revision(app_id)
        if active is None:
            raise LookupError(f"no active revision for app_id={app_id}")

        cached = self._active_graphs.get(app_id)
        if cached is not None and cached.revision == active.revision:
            return cached.graph

        snapshot = await self._revision_store.get_snapshot(app_id, active.revision)
        if snapshot is None:
            raise LookupError(
                f"missing revision snapshot for app_id={app_id}, revision={active.revision}"
            )

        graph = await self._compiler.compile(snapshot.spec)
        self._active_graphs[app_id] = CachedGraph(revision=active.revision, graph=graph)
        return graph

    async def warmup(self, app_id: str) -> None:
        await self.get_graph(app_id)

