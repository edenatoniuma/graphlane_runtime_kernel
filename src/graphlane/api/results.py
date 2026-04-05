from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TurnResult:
    turn_id: str
    session_id: str
    assistant_content: str = ""
    finish_reason: str | None = None
    tool_records: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

