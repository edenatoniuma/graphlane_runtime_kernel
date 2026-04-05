from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from graphlane.api.events import (
    EVENT_ASSISTANT_DELTA,
    EVENT_TOOL_END,
    EVENT_TOOL_START,
    TurnEvent,
)
from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec, ToolBinding


class ReactGraphState(TypedDict):
    app_id: str
    revision: int
    prompt: str
    query: str
    pending_tool_call: dict[str, Any] | None
    tool_records: list[dict[str, Any]]
    assistant_content: str
    metadata: dict[str, Any]
    traceparent: str | None


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _select_tool(query: str, tools: list[ToolBinding]) -> ToolBinding | None:
    normalized_query = _normalize_text(query)
    for tool in tools:
        tool_name = _normalize_text(tool.name)
        if not tool_name:
            continue
        if f"tool:{tool_name}" in normalized_query or tool_name in normalized_query:
            return tool
    return None


def _build_tool_call(tool: ToolBinding, query: str) -> dict[str, Any]:
    return {
        "run_id": uuid4().hex,
        "tool_id": tool.tool_id,
        "tool_name": tool.name,
        "input": query,
        "hidden_kwargs": dict(tool.hidden_kwargs),
    }


def _execute_tool(tool: ToolBinding, tool_call: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    output = {
        "tool_id": tool.tool_id,
        "tool_name": tool.name,
        "source": tool.source,
        "echo": str(tool_call["input"]),
        "hidden_kwargs": dict(tool.hidden_kwargs),
    }
    duration = time.perf_counter() - started_at
    return {
        "run_id": str(tool_call["run_id"]),
        "tool_name": tool.name,
        "input": str(tool_call["input"]),
        "output": json.dumps(output, ensure_ascii=False),
        "duration": round(duration, 4),
    }


def _build_initial_state(spec: AppSpec, request: TurnRequest) -> ReactGraphState:
    return ReactGraphState(
        app_id=spec.app_id,
        revision=spec.revision,
        prompt=spec.prompt or spec.name,
        query=request.query,
        pending_tool_call=None,
        tool_records=[],
        assistant_content="",
        metadata=dict(request.metadata),
        traceparent=request.traceparent,
    )


def _build_agent_node(spec: AppSpec):
    def agent_node(state: ReactGraphState) -> ReactGraphState:
        query = str(state["query"])
        selected_tool = _select_tool(query, spec.tools)
        if selected_tool is None:
            return ReactGraphState(
                pending_tool_call=None,
                assistant_content=f"{state['prompt']}: {query}",
            )

        return ReactGraphState(
            pending_tool_call=_build_tool_call(selected_tool, query),
            assistant_content="",
        )

    return agent_node


def _build_tools_node(spec: AppSpec):
    tool_index = {tool.tool_id: tool for tool in spec.tools}

    def tools_node(state: ReactGraphState) -> ReactGraphState:
        tool_call = state.get("pending_tool_call")
        if not isinstance(tool_call, dict):
            return ReactGraphState(tool_records=list(state.get("tool_records", [])))

        tool = tool_index.get(str(tool_call["tool_id"]))
        if tool is None:
            raise LookupError(f"missing tool binding for tool_id={tool_call['tool_id']}")

        tool_record = _execute_tool(tool, tool_call)
        tool_records = [*list(state.get("tool_records", [])), tool_record]
        return ReactGraphState(
            pending_tool_call=None,
            tool_records=tool_records,
        )

    return tools_node


def _finalize_node(state: ReactGraphState) -> ReactGraphState:
    assistant_content = str(state.get("assistant_content", ""))
    if assistant_content:
        return ReactGraphState(assistant_content=assistant_content)

    tool_records = list(state.get("tool_records", []))
    if not tool_records:
        return ReactGraphState(assistant_content="")

    latest_tool = tool_records[-1]
    prompt = str(state.get("prompt", ""))
    return ReactGraphState(
        assistant_content=f"{prompt}: {latest_tool['output']}",
    )


def _route_after_agent(state: ReactGraphState) -> str:
    if state.get("pending_tool_call"):
        return "tools"
    return "finalize"


@dataclass(slots=True)
class ReactCompiledGraph:
    app_id: str
    revision: int
    graph_factory: Callable[[], CompiledStateGraph]
    spec: AppSpec

    async def __call__(self, request: TurnRequest) -> str:
        graph = self.graph_factory()
        result = graph.invoke(_build_initial_state(self.spec, request))
        return str(result.get("assistant_content", ""))

    async def stream_events(self, request: TurnRequest):
        graph = self.graph_factory()
        result = graph.invoke(_build_initial_state(self.spec, request))
        tool_records = list(result.get("tool_records", []))
        if tool_records:
            latest_tool = dict(tool_records[-1])
            yield TurnEvent(
                type=EVENT_TOOL_START,
                payload={
                    "run_id": str(latest_tool["run_id"]),
                    "tool_name": str(latest_tool["tool_name"]),
                    "input": str(latest_tool["input"]),
                },
            )
            yield TurnEvent(
                type=EVENT_TOOL_END,
                payload=latest_tool,
            )

        assistant_content = str(result.get("assistant_content", ""))
        if assistant_content:
            yield TurnEvent(
                type=EVENT_ASSISTANT_DELTA,
                payload={"content": assistant_content},
            )


class ReactPatternCompiler:
    async def compile(self, spec: AppSpec) -> ReactCompiledGraph:
        def graph_factory() -> CompiledStateGraph:
            workflow = StateGraph(ReactGraphState)
            workflow.add_node("agent", _build_agent_node(spec))
            workflow.add_node("tools", _build_tools_node(spec))
            workflow.add_node("finalize", _finalize_node)
            workflow.set_entry_point("agent")
            workflow.add_conditional_edges(
                "agent",
                _route_after_agent,
                {
                    "tools": "tools",
                    "finalize": "finalize",
                },
            )
            workflow.add_edge("tools", "finalize")
            workflow.add_edge("finalize", END)
            return workflow.compile()

        return ReactCompiledGraph(
            app_id=spec.app_id,
            revision=spec.revision,
            graph_factory=graph_factory,
            spec=spec,
        )

    async def run(self, spec: AppSpec, request: TurnRequest) -> str:
        compiled = await self.compile(spec)
        return await compiled(request)
