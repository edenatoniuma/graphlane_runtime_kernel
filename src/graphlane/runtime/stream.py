from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from graphlane.api.events import EVENT_ASSISTANT_DELTA, EVENT_TOOL_END, EVENT_TOOL_START, TurnEvent
from graphlane.api.requests import TurnRequest


def stringify_event_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(stringify_event_value(item) for item in value)
    if isinstance(value, dict):
        text = value.get("text")
        if text is not None:
            return str(text)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, BaseMessage):
        return stringify_event_value(value.content)
    return str(value)


def extract_chat_model_output_text(output: Any) -> str:
    if isinstance(output, AIMessage):
        return stringify_event_value(output.content)
    return stringify_event_value(output)


class LangGraphEventAdapter:
    def __init__(self) -> None:
        self._model_streamed_visible_text: dict[str, bool] = {}
        self._pending_tools: dict[str, tuple[float, str, str]] = {}

    async def stream(
        self,
        graph: Any,
        request: TurnRequest,
    ) -> AsyncIterator[TurnEvent]:
        from langchain_core.messages import HumanMessage

        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=request.query)]},
            version="v2",
        ):
            kind = str(event["event"])
            data = event.get("data", {})
            name = str(event.get("name", ""))
            run_id = str(event.get("run_id", ""))

            if kind == "on_chat_model_start":
                self._model_streamed_visible_text[run_id] = False
                continue

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if not isinstance(chunk, AIMessageChunk):
                    continue
                content = stringify_event_value(chunk.content)
                if not content:
                    continue
                self._model_streamed_visible_text[run_id] = True
                yield TurnEvent(
                    type=EVENT_ASSISTANT_DELTA,
                    payload={"content": content},
                )
                continue

            if kind == "on_chat_model_end":
                emitted = self._model_streamed_visible_text.pop(run_id, False)
                if emitted:
                    continue
                output = data.get("output")
                content = extract_chat_model_output_text(output)
                if not content:
                    continue
                yield TurnEvent(
                    type=EVENT_ASSISTANT_DELTA,
                    payload={"content": content},
                )
                continue

            if kind == "on_tool_start":
                tool_input = stringify_event_value(data.get("input"))
                self._pending_tools[run_id] = (time.perf_counter(), name, tool_input)
                yield TurnEvent(
                    type=EVENT_TOOL_START,
                    payload={
                        "run_id": run_id,
                        "tool_name": name,
                        "input": tool_input,
                    },
                )
                continue

            if kind == "on_tool_end":
                started = self._pending_tools.pop(run_id, None)
                start_at, tool_name, tool_input = started or (
                    time.perf_counter(),
                    name,
                    stringify_event_value(data.get("input")),
                )
                yield TurnEvent(
                    type=EVENT_TOOL_END,
                    payload={
                        "run_id": run_id,
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": stringify_event_value(data.get("output")),
                        "duration": round(time.perf_counter() - start_at, 4),
                    },
                )
