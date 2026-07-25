"""Budget, stop conditions, and the final result of a loop run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from selfprompt.core.events import Turn


@dataclass
class Budget:
    """Hard limits on how far a loop is allowed to run.

    A loop stops the instant any one of these is exceeded, regardless of
    whether the goal was met. This is what keeps "autonomous" from meaning
    "unbounded."
    """

    max_turns: int = 25
    max_tokens: int | None = None
    max_cost_usd: float | None = None

    def exceeded_by(self, turns_used: int, tokens_used: int, cost_usd: float) -> str | None:
        if turns_used >= self.max_turns:
            return f"max_turns reached ({self.max_turns})"
        if self.max_tokens is not None and tokens_used >= self.max_tokens:
            return f"max_tokens reached ({self.max_tokens})"
        if self.max_cost_usd is not None and cost_usd >= self.max_cost_usd:
            return f"max_cost_usd reached (${self.max_cost_usd:.2f})"
        return None


@dataclass
class StopCondition:
    """A user-supplied predicate that ends the loop early, on success.

    `check` receives the list of turns so far and returns True when the goal
    is satisfied. Keeping this a plain callable (not a class hierarchy) is
    what lets any tool -- a test suite, a diff, a file's existence -- define
    "done."
    """

    name: str
    check: Callable[[list[Turn]], bool]

    def is_met(self, turns: list[Turn]) -> bool:
        return self.check(turns)


@dataclass
class LoopResult:
    """What a `GoalLoop.run()` call hands back."""

    goal: str
    turns: list[Turn]
    finished: bool
    stop_reason: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "finished": self.finished,
            "stop_reason": self.stop_reason,
            "turn_count": self.turn_count,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata,
        }
