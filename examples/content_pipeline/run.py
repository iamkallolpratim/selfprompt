"""Draft -> critique -> revise a piece of content until confidence is high.

Demonstrates: a confidence-based StopCondition -- the loop keeps revising
its own output until its self-reported confidence clears a bar, rather than
stopping after a fixed number of drafts.
"""

from __future__ import annotations

from selfprompt.connectors.client import SelfPromptClient
from selfprompt.core.llm import MockProvider
from selfprompt.core.state import Budget, StopCondition
from selfprompt.tools.registry import Permission


def confident_enough(turns) -> bool:
    return bool(turns) and turns[-1].critique.confidence >= 0.9


def main() -> None:
    llm = MockProvider(
        [
            '{"observation": "first draft written", '
            '"critique": {"progress_made": true, "confidence": 0.5, "issues": ["tone is too formal"]}, '
            '"action": {"type": "message", "detail": "Draft v1: ...formal announcement text..."}}',
            '{"observation": "revised for tone", '
            '"critique": {"progress_made": true, "confidence": 0.92, "issues": []}, '
            '"action": {"type": "message", "detail": "Draft v2 meets the bar: ...casual announcement text..."}}',
        ]
    )

    client = SelfPromptClient(llm=llm, permission_mode=Permission.ALLOW)
    result = client.run(
        "Write a product announcement blog post in a casual, confident tone.",
        goal_id="content-pipeline-demo",
        budget=Budget(max_turns=6),
        stop_conditions=[StopCondition("confident_enough", confident_enough)],
        on_message=print,
    )
    print(f"\n{'FINISHED' if result.finished else 'STOPPED'}: {result.stop_reason}")


if __name__ == "__main__":
    main()
