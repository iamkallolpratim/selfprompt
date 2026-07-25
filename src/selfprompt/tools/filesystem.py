"""File system tools: read, write, list. Writes are marked dangerous."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from selfprompt.tools.base import ToolResult


class ReadFileTool:
    name = "read_file"
    description = "Read the contents of a text file. Args: path (str)."
    dangerous = False

    def run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"])
        try:
            return ToolResult(ok=True, output=path.read_text(encoding="utf-8"))
        except OSError as exc:
            return ToolResult(ok=False, output="", error=str(exc))


class WriteFileTool:
    name = "write_file"
    description = "Write text content to a file, creating parent dirs. Args: path (str), content (str)."
    dangerous = True

    def run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"])
        content = kwargs.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(ok=True, output=f"wrote {len(content)} bytes to {path}")
        except OSError as exc:
            return ToolResult(ok=False, output="", error=str(exc))


class ListDirTool:
    name = "list_dir"
    description = "List entries in a directory. Args: path (str, default '.')."
    dangerous = False

    def run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs.get("path", "."))
        try:
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
            return ToolResult(ok=True, output="\n".join(entries), data={"entries": entries})
        except OSError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
