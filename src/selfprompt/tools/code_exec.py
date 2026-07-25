"""Sandboxed(-ish) Python execution tool.

Runs code in a fresh subprocess (not `exec()` in-process) so a crash or
infinite loop in generated code can't take down the loop itself. This is
process isolation, not a security sandbox -- don't run untrusted code from
the open internet through this without a real sandbox (container, gVisor,
etc.) in front of it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from selfprompt.tools.base import ToolResult


class PythonExecTool:
    name = "python_exec"
    description = "Execute a Python snippet in an isolated subprocess. Args: code (str), timeout (int, optional)."
    dangerous = True

    def run(self, **kwargs: Any) -> ToolResult:
        code = kwargs["code"]
        timeout = kwargs.get("timeout", 30)
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "snippet.py"
            script.write_text(code, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                ok = proc.returncode == 0
                return ToolResult(ok=ok, output=proc.stdout + proc.stderr)
            except subprocess.TimeoutExpired as exc:
                return ToolResult(ok=False, output="", error=f"timed out after {timeout}s: {exc}")
