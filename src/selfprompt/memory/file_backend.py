"""File-based memory: Markdown for humans, JSON for the loop.

Layout under `root` (default `.selfprompt/memory/`):

    <goal_id>/
        turns.jsonl     one JSON object per turn, append-only
        progress.md     human-readable running log, rewritten each turn
        lessons.md      distilled lessons extracted from failures/critiques

This is the default backend because it needs zero infrastructure: `git add`
it, read it in an editor, grep it. Sessions survive because the files do.
"""

from __future__ import annotations

import json
from pathlib import Path

from selfprompt.core.events import Action, ActionType, Critique, Observation, Turn


class FileMemory:
    def __init__(self, root: str | Path = ".selfprompt/memory") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _goal_dir(self, goal_id: str) -> Path:
        d = self.root / goal_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def record_turn(self, goal_id: str, turn: Turn) -> None:
        d = self._goal_dir(goal_id)
        with (d / "turns.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_dict()) + "\n")
        self._append_progress(d, turn)
        if not turn.critique.progress_made or turn.critique.issues:
            self._extract_lesson(d, turn)

    def _append_progress(self, d: Path, turn: Turn) -> None:
        progress = d / "progress.md"
        header = "# Progress Log\n\n" if not progress.exists() else ""
        entry = (
            f"## Turn {turn.index} — {turn.timestamp}\n"
            f"- **Observation:** {turn.observation.summary}\n"
            f"- **Critique:** progress={turn.critique.progress_made}, "
            f"confidence={turn.critique.confidence:.2f}\n"
            f"- **Action:** {turn.action.type.value} — {turn.action.detail}\n"
            f"- **Result:** {turn.result}\n\n"
        )
        with progress.open("a", encoding="utf-8") as f:
            f.write(header + entry)

    def _extract_lesson(self, d: Path, turn: Turn) -> None:
        if not turn.critique.issues:
            return
        lesson = (
            f"Turn {turn.index}: action `{turn.action.type.value}` "
            f"({turn.action.detail}) hit: {'; '.join(turn.critique.issues)}"
        )
        self.record_lesson(d.name, lesson, tags=["auto-extracted"])

    def record_lesson(self, goal_id: str, lesson: str, *, tags: list[str] | None = None) -> None:
        d = self._goal_dir(goal_id)
        lessons = d / "lessons.md"
        header = "# Lessons\n\n" if not lessons.exists() else ""
        tag_str = f" `{', '.join(tags)}`" if tags else ""
        with lessons.open("a", encoding="utf-8") as f:
            f.write(header + f"- {lesson}{tag_str}\n")

    def load_turns(self, goal_id: str) -> list[Turn]:
        d = self._goal_dir(goal_id)
        turns_file = d / "turns.jsonl"
        if not turns_file.exists():
            return []
        turns: list[Turn] = []
        for line in turns_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            turns.append(
                Turn(
                    index=raw["index"],
                    observation=Observation(summary=raw["observation"]),
                    critique=Critique(**raw["critique"]),
                    action=Action(
                        type=ActionType(raw["action"]["type"]),
                        detail=raw["action"]["detail"],
                        tool_name=raw["action"].get("tool_name"),
                        tool_args=raw["action"].get("tool_args") or {},
                        delegate_agent=raw["action"].get("delegate_agent"),
                    ),
                    result=raw.get("result", ""),
                    tokens_used=raw.get("tokens_used", 0),
                    cost_usd=raw.get("cost_usd", 0.0),
                    timestamp=raw.get("timestamp", ""),
                )
            )
        return turns

    def load_context(self, goal_id: str, *, max_chars: int = 4000) -> str:
        d = self._goal_dir(goal_id)
        parts = []
        lessons = d / "lessons.md"
        if lessons.exists():
            parts.append(lessons.read_text(encoding="utf-8"))
        progress = d / "progress.md"
        if progress.exists():
            text = progress.read_text(encoding="utf-8")
            parts.append(text[-max_chars:])
        blob = "\n\n".join(parts)
        return blob[-max_chars:] if len(blob) > max_chars else blob
