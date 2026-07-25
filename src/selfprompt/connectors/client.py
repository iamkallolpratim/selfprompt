"""Simple Python client: the one-import way to use SelfPrompt as a library.

    from selfprompt.connectors import SelfPromptClient

    client = SelfPromptClient()  # reads .selfprompt/config.yaml if present
    result = client.run("refactor the auth module to remove the global singleton")

This exists so embedding SelfPrompt inside another Python app (a bot, a CI
job, a bigger agent) doesn't require knowing about `GoalLoop`,
`ToolRegistry`, `FileMemory`, etc. individually.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from selfprompt.agents.orchestrator import Orchestrator
from selfprompt.agents.registry import load_all_agents
from selfprompt.core.llm import LLMProvider
from selfprompt.core.loop import GoalLoop
from selfprompt.core.state import Budget, LoopResult, StopCondition
from selfprompt.memory.file_backend import FileMemory
from selfprompt.tools.code_exec import PythonExecTool
from selfprompt.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from selfprompt.tools.git import GitTool
from selfprompt.tools.registry import Permission, ToolRegistry
from selfprompt.tools.shell import ShellTool


def default_tools() -> list:
    return [ReadFileTool(), WriteFileTool(), ListDirTool(), ShellTool(), GitTool(), PythonExecTool()]


class SelfPromptClient:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        tools: list | None = None,
        permission_mode: Permission = Permission.ASK,
        on_permission_request: Callable[[str, dict[str, Any]], bool] | None = None,
        memory_root: str | Path = ".selfprompt/memory",
        agents_dir: str | Path | None = ".selfprompt/agents",
        multi_agent: bool = False,
    ) -> None:
        self.llm = llm
        self.tools = ToolRegistry(
            tools if tools is not None else default_tools(),
            permission_mode=permission_mode,
            on_permission_request=on_permission_request,
        )
        self.memory = FileMemory(memory_root)
        self.orchestrator: Orchestrator | None = None
        if multi_agent:
            agents = load_all_agents(agents_dir)
            self.orchestrator = Orchestrator(agents, llm=llm, tool_registry=self.tools, memory=self.memory)

    def run(
        self,
        goal: str,
        *,
        goal_id: str | None = None,
        budget: Budget | None = None,
        stop_conditions: list[StopCondition] | None = None,
        system_prompt: str | None = None,
        on_message: Callable[[str], None] | None = None,
    ) -> LoopResult:
        loop = GoalLoop(
            goal,
            llm=self.llm,
            tools=self.tools,
            memory=self.memory,
            orchestrator=self.orchestrator,
            system_prompt=system_prompt,
            budget=budget,
            stop_conditions=stop_conditions,
            goal_id=goal_id,
            on_message=on_message or (lambda text: None),
        )
        return loop.run()
