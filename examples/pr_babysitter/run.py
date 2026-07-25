"""Babysit a pull request: check CI status, fix failures, repeat until green.

Demonstrates: a real-world "keep checking back" loop with a hard cost
budget (so an unattended babysitting job can't run away), and manual
wiring of a *separate* model/provider for the delegated `coder` specialist
than the one driving the main loop -- useful when e.g. the orchestrator
should think with a bigger model than its specialists.
"""

from __future__ import annotations

from selfprompt.agents.orchestrator import Orchestrator
from selfprompt.agents.registry import load_builtin_agents
from selfprompt.core.llm import MockProvider
from selfprompt.core.loop import GoalLoop
from selfprompt.core.state import Budget, StopCondition
from selfprompt.memory.file_backend import FileMemory
from selfprompt.tools.registry import Permission, ToolRegistry
from selfprompt.tools.shell import ShellTool


def ci_green(turns) -> bool:
    return bool(turns) and "ci: green" in turns[-1].result.lower()


def main() -> None:
    main_llm = MockProvider(
        [
            '{"observation": "checking CI status", '
            '"critique": {"progress_made": true, "confidence": 0.5, "issues": []}, '
            '"action": {"type": "tool_call", "detail": "check CI status", '
            '"tool_name": "shell", "tool_args": {"command": "echo \'CI: failing - lint error\'"}}}',
            '{"observation": "CI failing on lint, delegating a fix", '
            '"critique": {"progress_made": true, "confidence": 0.6, "issues": ["lint error in prior run"]}, '
            '"action": {"type": "delegate", "detail": "fix the lint error and push", "delegate_agent": "coder"}}',
            '{"observation": "re-checking CI after fix", '
            '"critique": {"progress_made": true, "confidence": 0.9, "issues": []}, '
            '"action": {"type": "tool_call", "detail": "check CI status again", '
            '"tool_name": "shell", "tool_args": {"command": "echo \'CI: green\'"}}}',
        ]
    )
    coder_llm = MockProvider(
        [
            '{"observation": "found the lint error, fixing it", '
            '"critique": {"progress_made": true, "confidence": 0.85, "issues": []}, '
            '"action": {"type": "finish", "detail": "fixed lint error and pushed the commit"}}',
        ]
    )

    tools = ToolRegistry([ShellTool()], permission_mode=Permission.ALLOW)
    memory = FileMemory(".selfprompt/memory")
    orchestrator = Orchestrator(load_builtin_agents(), llm=coder_llm, tool_registry=tools, memory=memory)

    loop = GoalLoop(
        "Babysit PR #42 until CI is green.",
        llm=main_llm,
        tools=tools,
        memory=memory,
        orchestrator=orchestrator,
        budget=Budget(max_turns=15, max_cost_usd=1.00),
        stop_conditions=[StopCondition("ci_green", ci_green)],
        goal_id="pr-babysitter-demo",
        on_message=print,
    )
    result = loop.run()
    print(f"\n{'FINISHED' if result.finished else 'STOPPED'}: {result.stop_reason}")


if __name__ == "__main__":
    main()
