from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any

EVENT_ASSISTANT_DELTA = "assistant_delta"
EVENT_TOOL_START = "tool_start"
EVENT_TOOL_END = "tool_end"
EVENT_PERFORMANCE_STATS = "performance_stats"
EVENT_ERROR = "error"
EVENT_DONE = "done"


@dataclass(slots=True)
class TurnEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TurnEvent":
        return cls(
            type=str(data["type"]),
            payload=dict(data.get("payload", {})),
            timestamp=float(data.get("timestamp", time())),
        )

