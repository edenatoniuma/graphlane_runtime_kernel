from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio.client import Redis

from graphlane.api.events import EVENT_DONE, TurnEvent


class RedisEventBus:
    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "graphlane:turn:stream",
        maxlen: int = 1000,
        read_block_ms: int = 1000,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._maxlen = maxlen
        self._read_block_ms = read_block_ms

    async def publish(self, turn_id: str, event: TurnEvent) -> None:
        stream_key = self._stream_key(turn_id)
        await self._redis.xadd(
            stream_key,
            {"event": json.dumps(event.to_dict(), ensure_ascii=False)},
            maxlen=self._maxlen,
            approximate=True,
        )

    async def subscribe(self, turn_id: str) -> AsyncIterator[TurnEvent]:
        stream_key = self._stream_key(turn_id)
        last_id = "0-0"
        while True:
            response = await self._redis.xread(
                {stream_key: last_id},
                block=self._read_block_ms,
                count=100,
            )
            if not response:
                continue

            for _, messages in response:
                for message_id, fields in messages:
                    last_id = self._decode(message_id)
                    raw_event = self._decode(fields.get("event"))
                    event = TurnEvent.from_dict(json.loads(raw_event))
                    yield event
                    if event.type == EVENT_DONE:
                        return

    def _stream_key(self, turn_id: str) -> str:
        return f"{self._key_prefix}:{turn_id}"

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

