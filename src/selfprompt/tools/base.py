"""Tool contract. Any callable that satisfies this can be registered."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    dangerous: bool  # requires explicit permission before it can run

    def run(self, **kwargs: Any) -> ToolResult: ...
