"""Event types exchanged in the Observation -> Critique -> Next Action cycle.

Every turn of the loop produces one `Turn`, which is the unit that gets
persisted to memory and shown to the user. Keeping this as plain dataclasses
(no framework base classes) is what makes the loop portable across Claude
Code, Codex, or a bare Python script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """What kind of thing the loop decided to do this turn."""

    TOOL_CALL = "tool_call"
    DELEGATE = "delegate"       # hand off to a sub-agent
    MESSAGE = "message"         # talk to the user / ask a question
    FINISH = "finish"           # declare the goal complete
    ABORT = "abort"             # give up, budget/stop condition hit


@dataclass(slots=True)
class Observation:
    """What the loop currently sees: goal state, prior results, environment."""

    summary: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Critique:
    """Self-assessment of progress before deciding the next action.

    This is the "verification is a first-class citizen" step: the loop is
    required to judge its own last action before it's allowed to act again.
    """

    progress_made: bool
    confidence: float  # 0.0-1.0
    issues: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(slots=True)
class Action:
    """The next thing to do, decided after observation + critique."""

    type: ActionType
    detail: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    delegate_agent: str | None = None


@dataclass(slots=True)
class Turn:
    """One full cycle of the loop, persisted verbatim to memory."""

    index: int
    observation: Observation
    critique: Critique
    action: Action
    result: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "observation": self.observation.summary,
            "critique": {
                "progress_made": self.critique.progress_made,
                "confidence": self.critique.confidence,
                "issues": self.critique.issues,
                "notes": self.critique.notes,
            },
            "action": {
                "type": self.action.type.value,
                "detail": self.action.detail,
                "tool_name": self.action.tool_name,
                "tool_args": self.action.tool_args,
                "delegate_agent": self.action.delegate_agent,
            },
            "result": self.result,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
        }
