from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from graphlane.api.events import EVENT_DONE, TurnEvent


@dataclass(slots=True)
class _TurnStream:
    events: list[TurnEvent] = field(default_factory=list)
    done: bool = False
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._streams: dict[str, _TurnStream] = {}

    async def publish(self, turn_id: str, event: TurnEvent) -> None:
        stream = self._streams.setdefault(turn_id, _TurnStream())
        async with stream.condition:
            stream.events.append(event)
            if event.type == EVENT_DONE:
                stream.done = True
            stream.condition.notify_all()

    async def subscribe(self, turn_id: str):
        stream = self._streams.setdefault(turn_id, _TurnStream())
        index = 0
        while True:
            async with stream.condition:
                while index >= len(stream.events) and not stream.done:
                    await stream.condition.wait()

                while index < len(stream.events):
                    event = stream.events[index]
                    index += 1
                    yield event

                if stream.done:
                    return

