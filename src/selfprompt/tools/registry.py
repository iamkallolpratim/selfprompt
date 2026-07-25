"""Tool registry with a permission model.

Safe defaults: tools flagged `dangerous` (shell, file writes, code exec,
non-read-only git) require an explicit grant before they run. Three modes:

    ALLOW  - dangerous tools run without asking (CI, sandboxes you trust)
    ASK    - a permission callback is consulted per call (interactive use)
    DENY   - dangerous tools are refused outright (fully read-only loops)

This mirrors the same posture as Claude Code's own permission system, on
purpose: SelfPrompt should never be more permissive than the host it runs
inside of.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from selfprompt.tools.base import Tool, ToolResult

PermissionCallback = Callable[[str, dict[str, Any]], bool]


class Permission(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def _deny_all(name: str, args: dict[str, Any]) -> bool:
    return False


class ToolRegistry:
    def __init__(
        self,
        tools: list[Tool] | None = None,
        *,
        permission_mode: Permission = Permission.ASK,
        on_permission_request: PermissionCallback | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.permission_mode = permission_mode
        self._on_permission_request = on_permission_request or _deny_all

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        lines = []
        for tool in self._tools.values():
            flag = " (dangerous)" if tool.dangerous else ""
            lines.append(f"- {tool.name}{flag}: {tool.description}")
        return "\n".join(lines)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, output="", error=f"unknown tool: {name}")

        if tool.dangerous:
            if self.permission_mode is Permission.DENY:
                return ToolResult(
                    ok=False, output="", error=f"tool '{name}' denied by permission_mode=DENY"
                )
            if self.permission_mode is Permission.ASK:
                granted = self._on_permission_request(name, kwargs)
                if not granted:
                    return ToolResult(
                        ok=False, output="", error=f"permission denied for tool '{name}'"
                    )

        try:
            return tool.run(**kwargs)
        except Exception as exc:  # noqa: BLE001 - tool failures must not crash the loop
            return ToolResult(ok=False, output="", error=f"{type(exc).__name__}: {exc}")
