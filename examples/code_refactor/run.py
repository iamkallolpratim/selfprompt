"""Refactor a file until its test suite passes.

Demonstrates: a StopCondition tied to real verification (a test run), not a
turn count -- the loop keeps going only as long as it needs to.
"""

from __future__ import annotations

from selfprompt.connectors.client import SelfPromptClient
from selfprompt.core.llm import MockProvider
from selfprompt.core.state import Budget, StopCondition
from selfprompt.tools.registry import Permission


def tests_pass(turns) -> bool:
    return bool(turns) and "passed" in turns[-1].result.lower() and "failed" not in turns[-1].result.lower()


def main() -> None:
    # Swap this for `AnthropicProvider()` to run against a real model.
    llm = MockProvider(
        [
            '{"observation": "reading the target module", '
            '"critique": {"progress_made": true, "confidence": 0.4, "issues": []}, '
            '"action": {"type": "tool_call", "detail": "run the test suite", '
            '"tool_name": "shell", "tool_args": {"command": "echo \'1 passed\'"}}}',
            '{"observation": "tests pass now", '
            '"critique": {"progress_made": true, "confidence": 0.95, "issues": []}, '
            '"action": {"type": "finish", "detail": "refactor verified by passing tests"}}',
        ]
    )

    client = SelfPromptClient(llm=llm, permission_mode=Permission.ALLOW)
    result = client.run(
        "Refactor payments/legacy.py to remove the global singleton, keeping tests green.",
        goal_id="code-refactor-demo",
        budget=Budget(max_turns=10),
        stop_conditions=[StopCondition("tests_pass", tests_pass)],
        on_message=print,
    )

    print(f"\n{'FINISHED' if result.finished else 'STOPPED'}: {result.stop_reason}")


if __name__ == "__main__":
    main()
