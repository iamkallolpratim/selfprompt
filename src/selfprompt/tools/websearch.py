"""Web search tool interface.

No bundled implementation ships by default (keeps the core dependency-light
and avoids picking a search vendor for you). Wrap whatever your host
provides -- Claude Code's WebSearch, an API key for Brave/Tavily/SerpAPI --
in a callable and pass it in.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from selfprompt.tools.base import ToolResult

SearchFn = Callable[[str], list[dict[str, str]]]


class WebSearchTool:
    name = "web_search"
    description = "Search the web. Args: query (str). Returns a list of {title, url, snippet}."
    dangerous = False

    def __init__(self, search_fn: SearchFn) -> None:
        self._search_fn = search_fn

    def run(self, **kwargs: Any) -> ToolResult:
        query = kwargs["query"]
        try:
            results = self._search_fn(query)
        except Exception as exc:  # noqa: BLE001 - surface any backend failure as a ToolResult
            return ToolResult(ok=False, output="", error=str(exc))
        output = "\n".join(f"- {r.get('title', '')} ({r.get('url', '')})" for r in results)
        return ToolResult(ok=True, output=output, data={"results": results})
