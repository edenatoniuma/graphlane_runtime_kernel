from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

TASK_GRAPH_PUBLISH = "graph_publish"
TASK_GRAPH_DESTROY = "graph_destroy"
TASK_CACHE_INVALIDATE = "cache_invalidate"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_DEAD = "dead"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SideEffectTask:
    task_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    traceparent: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = STATUS_PENDING
    retry_count: int = 0
    max_retries: int = 3
    next_run_at: datetime = field(default_factory=utc_now)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    claimed_at: datetime | None = None
    claimed_by: str | None = None
    last_error: str | None = None

    def mark_running(self, worker_id: str) -> None:
        now = utc_now()
        self.status = STATUS_RUNNING
        self.claimed_by = worker_id
        self.claimed_at = now
        self.updated_at = now

    def mark_done(self) -> None:
        self.status = STATUS_DONE
        self.updated_at = utc_now()

    def mark_retry(self, error_message: str, delay_seconds: float) -> None:
        now = utc_now()
        self.retry_count += 1
        self.status = STATUS_PENDING
        self.claimed_by = None
        self.last_error = error_message
        self.next_run_at = now + timedelta(seconds=delay_seconds)
        self.updated_at = now

    def mark_dead(self, error_message: str) -> None:
        now = utc_now()
        self.status = STATUS_DEAD
        self.claimed_by = None
        self.last_error = error_message
        self.updated_at = now

