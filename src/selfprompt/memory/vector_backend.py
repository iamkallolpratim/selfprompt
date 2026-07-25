"""Optional vector-backed memory for semantic recall over long histories.

This is a minimal, dependency-light reference implementation: it embeds text
with a user-supplied `embed_fn` and does cosine-similarity search in-process
with numpy. It is meant as a pluggable *starting point* -- swap `embed_fn`
for a real embedding model, or replace this whole class with a wrapper
around Chroma/Pinecone/pgvector, as long as it satisfies `MemoryBackend`.

Falls back gracefully: if numpy isn't installed, raise a clear error only
when this backend is actually instantiated (never at import time for the
rest of the package).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from selfprompt.core.events import Turn
from selfprompt.memory.file_backend import FileMemory

EmbedFn = Callable[[str], list[float]]


@dataclass(slots=True)
class _Record:
    text: str
    vector: list[float]
    goal_id: str


class VectorMemory:
    """Semantic-search memory layered on top of `FileMemory` for durability.

    All turns/lessons are still written to disk via `FileMemory` (so nothing
    is lost even without an embedding model configured); this class adds an
    in-memory vector index for `search()`.
    """

    def __init__(self, embed_fn: EmbedFn, root: str | Path = ".selfprompt/memory") -> None:
        try:
            import numpy  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "VectorMemory requires numpy: pip install selfprompt[vector]"
            ) from exc
        self._embed = embed_fn
        self._file = FileMemory(root)
        self._index: list[_Record] = []

    def record_turn(self, goal_id: str, turn: Turn) -> None:
        self._file.record_turn(goal_id, turn)
        text = f"{turn.observation.summary} | {turn.action.detail} | {turn.result}"
        self._index.append(_Record(text=text, vector=self._embed(text), goal_id=goal_id))

    def record_lesson(self, goal_id: str, lesson: str, *, tags: list[str] | None = None) -> None:
        self._file.record_lesson(goal_id, lesson, tags=tags)
        self._index.append(_Record(text=lesson, vector=self._embed(lesson), goal_id=goal_id))

    def load_turns(self, goal_id: str) -> list[Turn]:
        return self._file.load_turns(goal_id)

    def load_context(self, goal_id: str, *, max_chars: int = 4000) -> str:
        return self._file.load_context(goal_id, max_chars=max_chars)

    def search(self, query: str, *, goal_id: str | None = None, top_k: int = 5) -> list[str]:
        import numpy as np

        if not self._index:
            return []
        q = np.array(self._embed(query))
        candidates = [r for r in self._index if goal_id is None or r.goal_id == goal_id]
        if not candidates:
            return []
        mat = np.array([r.vector for r in candidates])
        sims = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)
        top = sims.argsort()[::-1][:top_k]
        return [candidates[i].text for i in top]
