from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import Annotated, TypedDict

from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec, ToolBinding


class ReactGraphState(TypedDict):
    messages: Annotated[list, add_messages]


def _stringify_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_stringify_content(item) for item in value)
    if isinstance(value, dict):
        text = value.get("text")
        if text is not None:
            return str(text)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, BaseMessage):
        return _stringify_content(value.content)
    return str(value)


def _build_tool(binding: ToolBinding) -> StructuredTool:
    async def tool_func(query: str) -> str:
        payload = {
            "tool_id": binding.tool_id,
            "tool_name": binding.name,
            "source": binding.source,
            "echo": query,
            "hidden_kwargs": dict(binding.hidden_kwargs),
        }
        return json.dumps(payload, ensure_ascii=False)

    return StructuredTool.from_function(
        coroutine=tool_func,
        name=binding.name,
        description=binding.description or f"Tool {binding.name}",
    )


def _build_chat_model(spec: AppSpec) -> BaseChatModel:
    model_args = dict(spec.model.model_args)
    streaming = bool(spec.runtime_options.get("streaming", True))
    return cast(
        BaseChatModel,
        init_chat_model(
            model=spec.model.model,
            streaming=streaming,
            model_provider=spec.model.provider,
            model_kwargs=dict(spec.model.model_kwargs),
            **model_args,
        ),
    )


def _build_model_call_node(
    llm_with_tools: Any,
    prompt_text: str,
) -> Callable[[ReactGraphState], Any]:
    async def agent_node(state: ReactGraphState) -> dict[str, list[AIMessage]]:
        messages = [SystemMessage(content=prompt_text), *state["messages"]]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    return agent_node


def _route_after_agent(state: ReactGraphState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def _build_initial_state(request: TurnRequest) -> ReactGraphState:
    from langchain_core.messages import HumanMessage

    return ReactGraphState(messages=[HumanMessage(content=request.query)])


class ReactPatternCompiler:
    async def compile(self, spec: AppSpec) -> CompiledStateGraph:
        prompt_text = spec.prompt or spec.name
        dynamic_tools = [_build_tool(binding) for binding in spec.tools]
        llm = _build_chat_model(spec)
        if dynamic_tools:
            bind_tools = getattr(llm, "bind_tools", None)
            if not callable(bind_tools):
                raise TypeError(
                    f"model provider={spec.model.provider!r} does not support bind_tools"
                )
            llm_with_tools = bind_tools(dynamic_tools)
        else:
            llm_with_tools = llm

        workflow = StateGraph(ReactGraphState)
        workflow.add_node(
            "agent",
            _build_model_call_node(llm_with_tools, prompt_text),
        )
        if dynamic_tools:
            workflow.add_node("tools", ToolNode(dynamic_tools))
        workflow.set_entry_point("agent")
        if dynamic_tools:
            workflow.add_conditional_edges(
                "agent",
                _route_after_agent,
                {"tools": "tools", END: END},
            )
            workflow.add_edge("tools", "agent")
        else:
            workflow.add_edge("agent", END)
        return workflow.compile()

    async def run(self, spec: AppSpec, request: TurnRequest) -> str:
        graph = await self.compile(spec)
        result = await graph.ainvoke(_build_initial_state(request))
        messages = cast(list[Any], result.get("messages", []))
        if not messages:
            return ""
        return _stringify_content(messages[-1])
