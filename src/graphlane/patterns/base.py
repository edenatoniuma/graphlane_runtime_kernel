from __future__ import annotations

from typing import Any, Protocol

from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec


class PatternCompiler(Protocol):
    async def compile(self, spec: AppSpec) -> Any: ...

    async def run(self, spec: AppSpec, request: TurnRequest) -> str: ...

