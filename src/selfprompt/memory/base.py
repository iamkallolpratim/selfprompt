"""Memory backend contract.

Memory is a first-class citizen of the loop, not an afterthought: every turn
gets persisted, lessons get extracted from failures, and a fresh loop run can
pick up context from a previous session. Any backend -- file-based (default),
vector, or a remote store -- just needs to satisfy this Protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from selfprompt.core.events import Turn


@runtime_checkable
class MemoryBackend(Protocol):
    def record_turn(self, goal_id: str, turn: Turn) -> None:
        """Persist one turn of a running loop."""
        ...

    def record_lesson(self, goal_id: str, lesson: str, *, tags: list[str] | None = None) -> None:
        """Persist a distilled lesson (usually extracted from a failure)."""
        ...

    def load_context(self, goal_id: str, *, max_chars: int = 4000) -> str:
        """Return a text blob to inject into the next prompt: prior progress,
        relevant lessons, and anything else the loop should remember."""
        ...

    def load_turns(self, goal_id: str) -> list[Turn]:
        """Return all turns previously recorded for this goal, in order."""
        ...
