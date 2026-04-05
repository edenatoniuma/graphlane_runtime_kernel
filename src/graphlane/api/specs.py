from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelSpec:
    provider: str
    model: str
    model_args: dict[str, Any] = field(default_factory=dict)
    model_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelSpec":
        return cls(
            provider=str(data["provider"]),
            model=str(data["model"]),
            model_args=dict(data.get("model_args", {})),
            model_kwargs=dict(data.get("model_kwargs", {})),
        )


@dataclass(slots=True)
class ToolBinding:
    tool_id: str
    name: str
    description: str
    source: str | None = None
    schema: dict[str, Any] | None = None
    hidden_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolBinding":
        return cls(
            tool_id=str(data["tool_id"]),
            name=str(data["name"]),
            description=str(data["description"]),
            source=data.get("source"),
            schema=None if data.get("schema") is None else dict(data["schema"]),
            hidden_kwargs=dict(data.get("hidden_kwargs", {})),
        )


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "revision": self.revision,
            "app_type": self.app_type,
            "model": self.model.to_dict(),
            "enabled_patterns": list(self.enabled_patterns),
            "prompt": self.prompt,
            "tools": [tool.to_dict() for tool in self.tools],
            "runtime_options": dict(self.runtime_options),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSpec":
        return cls(
            app_id=str(data["app_id"]),
            name=str(data["name"]),
            revision=int(data["revision"]),
            app_type=str(data["app_type"]),
            model=ModelSpec.from_dict(dict(data["model"])),
            enabled_patterns=[str(item) for item in data.get("enabled_patterns", [])],
            prompt=data.get("prompt"),
            tools=[ToolBinding.from_dict(dict(item)) for item in data.get("tools", [])],
            runtime_options=dict(data.get("runtime_options", {})),
        )
