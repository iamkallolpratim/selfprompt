"""Orchestrator: routes delegated sub-goals to the right specialist and runs
them as their own scoped `GoalLoop`.

This is what makes "multi-agent mode" just a configuration of single-agent
mode: a specialist is a `GoalLoop` with a narrower system prompt, a smaller
tool set, and a tighter turn budget. There is no separate multi-agent engine
to maintain.
"""

from __future__ import annotations

from selfprompt.agents.spec import AgentSpec
from selfprompt.core.llm import LLMProvider
from selfprompt.core.state import Budget, LoopResult
from selfprompt.memory.base import MemoryBackend
from selfprompt.tools.registry import ToolRegistry


class Orchestrator:
    def __init__(
        self,
        agents: dict[str, AgentSpec],
        *,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        memory: MemoryBackend | None = None,
    ) -> None:
        self.agents = agents
        self._llm = llm
        self._tool_registry = tool_registry
        self._memory = memory

    def route(self, sub_goal: str, *, hint: str | None = None) -> AgentSpec:
        """Pick the best-matching specialist for a delegated sub-goal.

        Routing is deliberately simple (keyword scoring) rather than another
        LLM call: it's fast, free, and debuggable. Pass `hint` (e.g. the
        action's declared `delegate_agent`) to short-circuit straight to a
        named agent.
        """
        if hint and hint in self.agents:
            return self.agents[hint]
        scored = sorted(self.agents.values(), key=lambda a: a.matches(sub_goal), reverse=True)
        if not scored or scored[0].matches(sub_goal) == 0:
            # No keyword match: fall back to the generic coder specialist if
            # present, else the first registered agent.
            return self.agents.get("coder", scored[0]) if scored else self._no_agents_error()
        return scored[0]

    def _no_agents_error(self) -> AgentSpec:
        raise ValueError("Orchestrator has no agents registered")

    def dispatch(
        self,
        sub_goal: str,
        *,
        agent_name: str | None = None,
        goal_id: str = "delegated",
    ) -> LoopResult:
        """Run `sub_goal` to completion under the chosen specialist and
        return its `LoopResult`. Imported lazily to avoid a core<->agents
        import cycle (core.loop never imports agents).
        """
        from selfprompt.core.loop import GoalLoop

        spec = self.route(sub_goal, hint=agent_name)
        found_tools = [self._tool_registry.get(n) for n in spec.tools]
        scoped_tools = ToolRegistry(
            tools=[t for t in found_tools if t is not None],
            permission_mode=self._tool_registry.permission_mode,
            on_permission_request=self._tool_registry._on_permission_request,
        )
        sub_loop = GoalLoop(
            goal=sub_goal,
            llm=self._llm,
            tools=scoped_tools,
            memory=self._memory,
            system_prompt=spec.system_prompt,
            budget=Budget(max_turns=spec.max_turns),
            goal_id=f"{goal_id}:{spec.name}",
        )
        return sub_loop.run()
