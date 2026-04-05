from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelSpec:
    provider: str
    model: str
    model_args: dict[str, Any] = field(default_factory=dict)
    model_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolBinding:
    tool_id: str
    name: str
    description: str
    source: str | None = None
    schema: dict[str, Any] | None = None
    hidden_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppSpec:
    app_id: str
    name: str
    revision: int
    app_type: str
    model: ModelSpec
    enabled_patterns: list[str] = field(default_factory=list)
    prompt: str | None = None
    tools: list[ToolBinding] = field(default_factory=list)
    runtime_options: dict[str, Any] = field(default_factory=dict)

