"""Claude Code integration glue.

Two things live here:

1. `claude_code_provider()` -- wraps a host-supplied completion function
   (the model call Claude Code already has loaded) as an `LLMProvider`, so
   `/goal` inside a Claude Code session doesn't spin up a second billed
   model. See `.claude/skills/selfprompt/SKILL.md` for the skill that calls
   this.
2. `run_goal_from_skill()` -- the single entry point the SKILL.md script
   invokes: parse the CLI-style args a skill receives, run the loop, and
   return a plain string suitable for printing back into the chat.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from selfprompt.connectors.client import SelfPromptClient
from selfprompt.core.llm import CallbackProvider
from selfprompt.core.state import Budget
from selfprompt.tools.registry import Permission

HostCompleteFn = Callable[[str, str | None], str]


def claude_code_provider(complete_fn: HostCompleteFn) -> CallbackProvider:
    """Wrap the host's own completion function as an `LLMProvider`.

    `complete_fn(prompt, system) -> str` is whatever the host exposes --
    e.g. a thin wrapper around the Claude Code agent SDK's message call.
    """
    return CallbackProvider(complete_fn)


def run_goal_from_skill(
    goal: str,
    *,
    complete_fn: HostCompleteFn,
    max_turns: int = 25,
    multi_agent: bool = False,
    permission_mode: str = "ask",
    on_permission_request: Callable[[str, dict[str, Any]], bool] | None = None,
) -> str:
    """Entry point for the `/goal` Claude Code skill.

    Runs to completion (bounded by `max_turns`) and returns a short summary
    string plus the final turn's result -- meant to be printed directly into
    the chat transcript by the skill script.
    """
    client = SelfPromptClient(
        llm=claude_code_provider(complete_fn),
        permission_mode=Permission(permission_mode),
        on_permission_request=on_permission_request,
        multi_agent=multi_agent,
    )
    result = client.run(goal, budget=Budget(max_turns=max_turns))
    last_result = result.turns[-1].result if result.turns else "(no turns run)"
    status = "✅ finished" if result.finished else "⏸ stopped"
    return (
        f"{status}: {result.stop_reason}\n"
        f"Turns: {result.turn_count}  Tokens: {result.total_tokens}\n\n"
        f"Last result:\n{last_result}"
    )
