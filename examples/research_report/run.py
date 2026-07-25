"""Produce a research report by delegating to the `researcher` specialist,
then writing the result to disk.

Demonstrates: multi-agent mode (orchestrator + specialist) and file output
as the definition of "done".
"""

from __future__ import annotations

from selfprompt.core.llm import MockProvider
from selfprompt.core.state import Budget
from selfprompt.connectors.client import SelfPromptClient
from selfprompt.tools.registry import Permission


def main() -> None:
    llm = MockProvider(
        [
            '{"observation": "need background on the topic first", '
            '"critique": {"progress_made": true, "confidence": 0.3, "issues": []}, '
            '"action": {"type": "delegate", "detail": "research current approaches to agentic loop budgeting", '
            '"delegate_agent": "researcher"}}',
            '{"observation": "have research findings, writing report", '
            '"critique": {"progress_made": true, "confidence": 0.8, "issues": []}, '
            '"action": {"type": "tool_call", "detail": "write the report", '
            '"tool_name": "write_file", '
            '"tool_args": {"path": "out/report.md", "content": "# Report\\n\\nFindings summarized here."}}}',
            '{"observation": "report written", '
            '"critique": {"progress_made": true, "confidence": 0.95, "issues": []}, '
            '"action": {"type": "finish", "detail": "report saved to out/report.md"}}',
        ]
    )

    client = SelfPromptClient(llm=llm, permission_mode=Permission.ALLOW, multi_agent=True)
    result = client.run(
        "Write a short report on best practices for budgeting autonomous agent loops.",
        goal_id="research-report-demo",
        budget=Budget(max_turns=10),
        on_message=print,
    )
    print(f"\n{'FINISHED' if result.finished else 'STOPPED'}: {result.stop_reason}")


if __name__ == "__main__":
    main()
