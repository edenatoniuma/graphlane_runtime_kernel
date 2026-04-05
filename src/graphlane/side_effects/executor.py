from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from graphlane.side_effects.tasks import SideEffectTask

SideEffectHandler = Callable[[SideEffectTask], Any]


class SideEffectExecutor:
    def __init__(self) -> None:
        self._handlers: dict[str, SideEffectHandler] = {}

    def register(self, task_type: str, handler: SideEffectHandler) -> None:
        self._handlers[task_type] = handler

    async def execute(self, task: SideEffectTask) -> None:
        handler = self._handlers.get(task.task_type)
        if handler is None:
            raise ValueError(f"no side effect handler registered for task_type={task.task_type}")

        result = handler(task)
        if inspect.isawaitable(result):
            await result

