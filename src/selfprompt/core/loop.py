"""The engine: a goal-driven Observation -> Critique -> Next Action loop.

This is the entire "product" of SelfPrompt. Everything else (memory, tools,
sub-agents, connectors) exists to feed or be called by this loop. The loop
itself has no opinion about which model, which tools, or which host
(Claude Code, Codex, a bare script) it runs inside of -- it only needs an
`LLMProvider` and, optionally, a `ToolRegistry`, a `MemoryBackend`, and an
`Orchestrator` for delegation.

Each turn:
  1. Observe  - summarize goal state + recent history + memory context.
  2. Ask the model for a structured decision: observation, self-critique,
     and exactly one next action.
  3. Critique - the model's own progress/confidence/issues judgement is
     required *before* it's allowed to act again. A turn with
     `progress_made=False` or non-empty `issues` gets its lesson persisted.
  4. Act - execute a tool call, delegate to a specialist, message the user,
     or finish/abort.

The loop stops the moment a `Budget` limit or a `StopCondition` is hit,
never runs unbounded, and persists every turn so a killed process can be
resumed by pointing a new `GoalLoop` at the same `goal_id`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from selfprompt.agents.orchestrator import Orchestrator
from selfprompt.core.events import Action, ActionType, Critique, Observation, Turn
from selfprompt.core.llm import LLMProvider
from selfprompt.core.state import Budget, LoopResult, StopCondition
from selfprompt.memory.base import MemoryBackend
from selfprompt.tools.registry import ToolRegistry

MessageCallback = Callable[[str], None]

_DEFAULT_SYSTEM_PROMPT = """\
You are an autonomous agent operating inside a self-prompting loop. You will
be given a GOAL, the tools available to you, and a history of what has
happened so far. Each turn you must respond with a single JSON object
(no markdown fences, no commentary outside the JSON) with this exact shape:

{
  "observation": "<one paragraph: what is the current state of the goal>",
  "critique": {
    "progress_made": <true|false, about the PREVIOUS action, or true if this is turn 1>,
    "confidence": <0.0-1.0, your confidence the goal will be met>,
    "issues": ["<any problems, blockers, or mistakes you notice>"],
    "notes": "<anything else worth recording>"
  },
  "action": {
    "type": "tool_call" | "delegate" | "message" | "finish" | "abort",
    "detail": "<human-readable description of what you're doing and why>",
    "tool_name": "<required if type == tool_call>",
    "tool_args": {"...": "..."},
    "delegate_agent": "<optional agent name if type == delegate>"
  }
}

Rules:
- Use "finish" only when the goal is verifiably complete -- verify, don't assume.
- Use "abort" if the goal is unreachable or you are stuck in a loop with no new ideas.
- Use "delegate" to hand a well-scoped sub-goal to a specialist agent.
- Prefer the smallest next action that makes verifiable progress.
"""


class GoalLoop:
    def __init__(
        self,
        goal: str,
        *,
        llm: LLMProvider,
        tools: ToolRegistry | None = None,
        memory: MemoryBackend | None = None,
        orchestrator: Orchestrator | None = None,
        system_prompt: str | None = None,
        budget: Budget | None = None,
        stop_conditions: list[StopCondition] | None = None,
        goal_id: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> None:
        self.goal = goal
        self._llm = llm
        self._tools = tools or ToolRegistry()
        self._memory = memory
        self._orchestrator = orchestrator
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.budget = budget or Budget()
        self.stop_conditions = stop_conditions or []
        self.goal_id = goal_id or _slugify(goal)
        self._on_message = on_message or (lambda text: None)

    # -- public API ---------------------------------------------------

    def run(self) -> LoopResult:
        turns: list[Turn] = list(self._memory.load_turns(self.goal_id)) if self._memory else []
        start_index = turns[-1].index + 1 if turns else 0
        total_tokens = sum(t.tokens_used for t in turns)
        total_cost = sum(t.cost_usd for t in turns)
        finished = False
        stop_reason = ""

        for i in range(start_index, start_index + self.budget.max_turns):
            exceeded = self.budget.exceeded_by(i - start_index, total_tokens, total_cost)
            if exceeded:
                stop_reason = exceeded
                break

            met = next((sc for sc in self.stop_conditions if sc.is_met(turns)), None)
            if met:
                finished = True
                stop_reason = f"stop condition met: {met.name}"
                break

            prompt = self._build_prompt(turns)
            response = self._llm.complete(prompt, system=self._system_prompt)
            total_tokens += response.total_tokens
            total_cost += response.cost_usd

            observation, critique, action = _parse_decision(response.text)
            result_text = self._execute(action)

            turn = Turn(
                index=i,
                observation=observation,
                critique=critique,
                action=action,
                result=result_text,
                tokens_used=response.total_tokens,
                cost_usd=response.cost_usd,
            )
            turns.append(turn)
            if self._memory:
                self._memory.record_turn(self.goal_id, turn)

            if action.type is ActionType.FINISH:
                finished = True
                stop_reason = "model declared goal complete"
                break
            if action.type is ActionType.ABORT:
                stop_reason = f"model aborted: {action.detail}"
                break
        else:
            stop_reason = stop_reason or f"max_turns reached ({self.budget.max_turns})"

        return LoopResult(
            goal=self.goal,
            turns=turns,
            finished=finished,
            stop_reason=stop_reason or "budget exhausted",
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
        )

    def next_step(self) -> dict[str, Any]:
        """Return the next prompt to answer, or signal the loop is already
        done -- without calling an `LLMProvider`.

        This is the host-driven counterpart to `run()`: for a caller that IS
        the model (e.g. Claude Code answering `/selfprompt` on the user's
        own subscription instead of a second billed API key), call this,
        decide the JSON turn yourself using the same contract described in
        `_DEFAULT_SYSTEM_PROMPT`, perform the action with your own tools,
        then hand the result to `record_step`.
        """
        turns = list(self._memory.load_turns(self.goal_id)) if self._memory else []

        if turns and turns[-1].action.type is ActionType.FINISH:
            return {"done": True, "stop_reason": "model declared goal complete"}
        if turns and turns[-1].action.type is ActionType.ABORT:
            return {"done": True, "stop_reason": f"model aborted: {turns[-1].action.detail}"}

        total_tokens = sum(t.tokens_used for t in turns)
        total_cost = sum(t.cost_usd for t in turns)

        exceeded = self.budget.exceeded_by(len(turns), total_tokens, total_cost)
        if exceeded:
            return {"done": True, "stop_reason": exceeded}

        met = next((sc for sc in self.stop_conditions if sc.is_met(turns)), None)
        if met:
            return {"done": True, "stop_reason": f"stop condition met: {met.name}"}

        return {
            "done": False,
            "goal_id": self.goal_id,
            "turn_index": len(turns),
            "system_prompt": self._system_prompt,
            "prompt": self._build_prompt(turns),
        }

    def record_step(
        self,
        *,
        turn_index: int,
        observation: str,
        critique: dict[str, Any],
        action: dict[str, Any],
        result: str,
    ) -> dict[str, Any]:
        """Persist one turn whose decision and result were produced
        externally. Companion to `next_step` -- see its docstring.
        """
        obs = Observation(summary=observation)
        crit = Critique(
            progress_made=bool(critique.get("progress_made", True)),
            confidence=float(critique.get("confidence", 0.5)),
            issues=list(critique.get("issues", [])),
            notes=critique.get("notes", ""),
        )
        act = Action(
            type=ActionType(action["type"]),
            detail=action.get("detail", ""),
            tool_name=action.get("tool_name"),
            tool_args=action.get("tool_args") or {},
            delegate_agent=action.get("delegate_agent"),
        )
        turn = Turn(index=turn_index, observation=obs, critique=crit, action=act, result=result)
        if self._memory:
            self._memory.record_turn(self.goal_id, turn)

        finished = act.type is ActionType.FINISH
        aborted = act.type is ActionType.ABORT
        stop_reason = None
        if finished:
            stop_reason = "model declared goal complete"
        elif aborted:
            stop_reason = f"model aborted: {act.detail}"
        return {"finished": finished, "aborted": aborted, "stop_reason": stop_reason}

    # -- internals ------------------------------------------------------

    def _build_prompt(self, turns: list[Turn]) -> str:
        parts = [f"GOAL:\n{self.goal}\n"]

        if self._tools.names():
            parts.append(f"AVAILABLE TOOLS:\n{self._tools.describe()}\n")

        if self._memory:
            context = self._memory.load_context(self.goal_id)
            if context:
                parts.append(f"MEMORY (prior progress + lessons):\n{context}\n")

        recent = turns[-5:]
        if recent:
            history_lines = []
            for t in recent:
                history_lines.append(
                    f"Turn {t.index}: action={t.action.type.value} "
                    f"({t.action.detail}) -> result: {t.result[:500]}"
                )
            parts.append("RECENT HISTORY:\n" + "\n".join(history_lines) + "\n")
        else:
            parts.append("RECENT HISTORY:\n(none -- this is the first turn)\n")

        parts.append("Respond with the JSON decision object now.")
        return "\n".join(parts)

    def _execute(self, action: Action) -> str:
        if action.type is ActionType.TOOL_CALL:
            if not action.tool_name:
                return "error: tool_call action missing tool_name"
            result = self._tools.call(action.tool_name, **action.tool_args)
            self._on_message(f"[tool:{action.tool_name}] {result.output or result.error}")
            return result.output if result.ok else f"ERROR: {result.error}"

        if action.type is ActionType.DELEGATE:
            if not self._orchestrator:
                return "error: delegate action requested but no orchestrator is configured"
            sub_result = self._orchestrator.dispatch(
                action.detail, agent_name=action.delegate_agent, goal_id=self.goal_id
            )
            self._on_message(f"[delegate:{action.delegate_agent or 'auto'}] {sub_result.stop_reason}")
            last = sub_result.turns[-1].result if sub_result.turns else ""
            return f"delegate finished={sub_result.finished} ({sub_result.stop_reason}): {last}"

        if action.type is ActionType.MESSAGE:
            self._on_message(action.detail)
            return action.detail

        if action.type is ActionType.FINISH:
            return "goal marked complete"

        if action.type is ActionType.ABORT:
            return f"aborted: {action.detail}"

        return "error: unknown action type"


# -- decision parsing -----------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    fenced = _JSON_FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in model response")
    return json.loads(candidate[start : end + 1])


def _parse_decision(text: str) -> tuple[Observation, Critique, Action]:
    try:
        data = _extract_json(text)
        observation = Observation(summary=data.get("observation", ""))
        c = data.get("critique", {})
        critique = Critique(
            progress_made=bool(c.get("progress_made", True)),
            confidence=float(c.get("confidence", 0.5)),
            issues=list(c.get("issues", [])),
            notes=c.get("notes", ""),
        )
        a = data["action"]
        action = Action(
            type=ActionType(a["type"]),
            detail=a.get("detail", ""),
            tool_name=a.get("tool_name"),
            tool_args=a.get("tool_args") or {},
            delegate_agent=a.get("delegate_agent"),
        )
        return observation, critique, action
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        # A malformed response is treated as a message, not a crash: the loop
        # records the raw text and lets the budget/stop-condition machinery
        # decide whether to keep going.
        observation = Observation(summary="model response was not valid JSON")
        critique = Critique(
            progress_made=False,
            confidence=0.0,
            issues=[f"failed to parse model decision: {exc}"],
        )
        action = Action(type=ActionType.MESSAGE, detail=text.strip()[:2000])
        return observation, critique, action


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "goal"
