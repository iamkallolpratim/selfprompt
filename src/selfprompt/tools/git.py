"""Git tool: a narrow, safer wrapper over `git` for common loop actions.

Deliberately does not expose `push --force`, `reset --hard`, or branch
deletion -- those stay in the "ask the human" category per SelfPrompt's
safety defaults. Anything else can be reached via ShellTool if a user opts
in explicitly.
"""

from __future__ import annotations

import subprocess
from typing import Any

from selfprompt.tools.base import ToolResult

_ALLOWED_SUBCOMMANDS = {"status", "diff", "log", "add", "commit", "branch", "show"}


class GitTool:
    name = "git"
    description = (
        "Run a safe subset of git commands (status, diff, log, add, commit, branch, show). "
        "Args: subcommand (str), args (list[str], optional)."
    )
    dangerous = True

    def run(self, **kwargs: Any) -> ToolResult:
        subcommand = kwargs["subcommand"]
        if subcommand not in _ALLOWED_SUBCOMMANDS:
            return ToolResult(
                ok=False,
                output="",
                error=f"'{subcommand}' is not allowed via GitTool; use ShellTool if you really need it.",
            )
        args = kwargs.get("args", [])
        try:
            proc = subprocess.run(
                ["git", subcommand, *args],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            ok = proc.returncode == 0
            return ToolResult(ok=ok, output=proc.stdout + proc.stderr)
        except OSError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
