"""Shell execution tool. Always dangerous -- runs through the permission model."""

from __future__ import annotations

import subprocess
from typing import Any

from selfprompt.tools.base import ToolResult


class ShellTool:
    name = "shell"
    description = "Run a shell command and capture stdout/stderr. Args: command (str), timeout (int, optional)."
    dangerous = True

    def run(self, **kwargs: Any) -> ToolResult:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", 60)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            ok = proc.returncode == 0
            output = proc.stdout + (proc.stderr if proc.stderr else "")
            return ToolResult(ok=ok, output=output, data={"returncode": proc.returncode})
        except subprocess.TimeoutExpired as exc:
            return ToolResult(ok=False, output="", error=f"timed out after {timeout}s: {exc}")
