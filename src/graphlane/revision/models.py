from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from graphlane.api.specs import AppSpec


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RevisionSnapshot:
    app_id: str
    revision: int
    spec: AppSpec
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ActiveRevision:
    app_id: str
    revision: int
    updated_at: datetime = field(default_factory=utc_now)

