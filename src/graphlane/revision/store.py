from __future__ import annotations

from collections import defaultdict

from graphlane.revision.models import ActiveRevision, RevisionSnapshot


class InMemoryRevisionStore:
    def __init__(self) -> None:
        self._snapshots: dict[str, dict[int, RevisionSnapshot]] = defaultdict(dict)
        self._active_revisions: dict[str, ActiveRevision] = {}

    async def save_snapshot(self, snapshot: RevisionSnapshot) -> None:
        self._snapshots[snapshot.app_id][snapshot.revision] = snapshot

    async def get_snapshot(
        self, app_id: str, revision: int
    ) -> RevisionSnapshot | None:
        return self._snapshots.get(app_id, {}).get(revision)

    async def set_active_revision(self, app_id: str, revision: int) -> None:
        self._active_revisions[app_id] = ActiveRevision(app_id=app_id, revision=revision)

    async def get_active_revision(self, app_id: str) -> ActiveRevision | None:
        return self._active_revisions.get(app_id)

    async def clear_active_revision(self, app_id: str) -> None:
        self._active_revisions.pop(app_id, None)
