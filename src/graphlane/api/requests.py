from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TurnRequest:
    app_id: str
    session_id: str
    query: str
    turn_id: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    traceparent: str | None = None

