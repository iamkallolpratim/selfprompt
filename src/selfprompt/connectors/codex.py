"""OpenAI Codex / Agents-SDK-style integration.

Exposes SelfPrompt as a single function-callable tool with a JSON schema,
matching the shape both the OpenAI Agents SDK and plain Chat Completions
function-calling expect. Register `SELFPROMPT_TOOL_SCHEMA` as a tool/function
definition, and route calls to it through `handle_tool_call`.
"""

from __future__ import annotations

from typing import Any

from selfprompt.connectors.client import SelfPromptClient
from selfprompt.core.llm import LLMProvider
from selfprompt.core.state import Budget
from selfprompt.tools.registry import Permission

SELFPROMPT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "selfprompt_run_goal",
        "description": (
            "Pursue a goal autonomously via a bounded self-prompting loop with "
            "persistent memory, instead of manually chaining prompts. Use for "
            "multi-step tasks with a clear definition of done."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The goal to pursue."},
                "max_turns": {
                    "type": "integer",
                    "description": "Hard cap on loop iterations.",
                    "default": 25,
                },
                "multi_agent": {
                    "type": "boolean",
                    "description": "Route sub-goals to specialist agents (coder, researcher, reviewer, ...).",
                    "default": False,
                },
            },
            "required": ["goal"],
        },
    },
}


def handle_tool_call(arguments: dict[str, Any], *, llm: LLMProvider) -> dict[str, Any]:
    """Execute a `selfprompt_run_goal` function call and return a JSON-able dict.

    `llm` is the model backend Codex/your app already has configured
    (an `AnthropicProvider`, `OpenAIProvider`, or any custom `LLMProvider`).
    """
    goal = arguments["goal"]
    max_turns = arguments.get("max_turns", 25)
    multi_agent = arguments.get("multi_agent", False)

    client = SelfPromptClient(llm=llm, permission_mode=Permission.ALLOW, multi_agent=multi_agent)
    result = client.run(goal, budget=Budget(max_turns=max_turns))
    return result.to_dict()
