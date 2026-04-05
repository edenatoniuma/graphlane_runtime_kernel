from __future__ import annotations

from typing import Any

from graphlane.api.requests import TurnRequest
from graphlane.api.specs import AppSpec
from graphlane.patterns.base import PatternCompiler

APP_TYPE_REACT = "REACT"
APP_TYPE_FREE = "FREE"
SUPPORTED_APP_TYPES = {APP_TYPE_REACT, APP_TYPE_FREE}
SUPPORTED_WORKER_PATTERNS = {APP_TYPE_REACT}


def normalize_app_type(value: str | None) -> str:
    if value is None:
        return APP_TYPE_REACT
    normalized = str(value).strip().upper()
    return normalized or APP_TYPE_REACT


def normalize_enabled_patterns(values: list[str] | None) -> list[str]:
    if not values:
        return [APP_TYPE_REACT]
    normalized: list[str] = []
    for value in values:
        pattern = normalize_app_type(value)
        if pattern not in normalized:
            normalized.append(pattern)
    return normalized


def validate_topology(app_type: str | None, enabled_patterns: list[str] | None) -> tuple[str, list[str]]:
    normalized_app_type = normalize_app_type(app_type)
    normalized_patterns = normalize_enabled_patterns(enabled_patterns)

    if normalized_app_type not in SUPPORTED_APP_TYPES:
        raise ValueError(f"unsupported app_type={normalized_app_type}")

    unsupported_patterns = [
        pattern for pattern in normalized_patterns if pattern not in SUPPORTED_WORKER_PATTERNS
    ]
    if unsupported_patterns:
        raise ValueError(f"unsupported enabled_patterns={unsupported_patterns}")

    if normalized_app_type != APP_TYPE_FREE and normalized_app_type not in normalized_patterns:
        raise ValueError(
            f"enabled_patterns must contain current app_type={normalized_app_type} when not FREE"
        )

    return normalized_app_type, normalized_patterns


class PatternRegistry:
    def __init__(self, compilers: dict[str, PatternCompiler] | None = None) -> None:
        self._compilers = dict(compilers or {})

    def register(self, pattern_name: str, compiler: PatternCompiler) -> None:
        self._compilers[normalize_app_type(pattern_name)] = compiler

    def get(self, pattern_name: str) -> PatternCompiler:
        normalized = normalize_app_type(pattern_name)
        compiler = self._compilers.get(normalized)
        if compiler is None:
            raise LookupError(f"no compiler registered for pattern={normalized}")
        return compiler

    async def compile(self, spec: AppSpec) -> Any:
        app_type, enabled_patterns = validate_topology(spec.app_type, spec.enabled_patterns)
        if app_type == APP_TYPE_FREE:
            return await self._compile_free_mode(spec, enabled_patterns)
        return await self.get(app_type).compile(spec)

    async def run(self, spec: AppSpec, request: TurnRequest) -> str:
        app_type, enabled_patterns = validate_topology(spec.app_type, spec.enabled_patterns)
        if app_type == APP_TYPE_FREE:
            return await self._run_free_mode(spec, request, enabled_patterns)
        return await self.get(app_type).run(spec, request)

    async def _compile_free_mode(self, spec: AppSpec, enabled_patterns: list[str]) -> Any:
        selected_pattern = enabled_patterns[0]
        return await self.get(selected_pattern).compile(spec)

    async def _run_free_mode(
        self,
        spec: AppSpec,
        request: TurnRequest,
        enabled_patterns: list[str],
    ) -> str:
        selected_pattern = enabled_patterns[0]
        return await self.get(selected_pattern).run(spec, request)

