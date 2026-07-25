# Architecture

## Overview

```mermaid
sequenceDiagram
    participant Host as Host (CLI / Claude Code / Codex / script)
    participant Loop as GoalLoop
    participant LLM as LLMProvider
    participant Mem as MemoryBackend
    participant Tools as ToolRegistry
    participant Orch as Orchestrator

    Host->>Loop: run(goal, budget, stop_conditions)
    loop each turn, until budget/stop condition
        Loop->>Mem: load_context(goal_id)
        Mem-->>Loop: prior progress + lessons
        Loop->>LLM: complete(prompt, system)
        LLM-->>Loop: {observation, critique, action}
        alt action.type == tool_call
            Loop->>Tools: call(tool_name, **args)
            Tools-->>Loop: ToolResult
        else action.type == delegate
            Loop->>Orch: dispatch(sub_goal, agent_name)
            Orch->>Orch: route() -> AgentSpec
            Orch->>Loop: new scoped GoalLoop.run()
            Orch-->>Loop: LoopResult
        else action.type == message/finish/abort
            Note over Loop: no external call
        end
        Loop->>Mem: record_turn(goal_id, turn)
    end
    Loop-->>Host: LoopResult
```

## Why a single `GoalLoop` class instead of a multi-agent framework

Multi-agent frameworks typically introduce a second engine (a "crew" or
"graph" runner) layered on top of a single-agent loop. SelfPrompt avoids
that: a specialist is just a `GoalLoop` configured with a narrower
`system_prompt`, a smaller `ToolRegistry`, and a tighter `Budget`. The
`Orchestrator` doesn't run agents itself — it constructs a scoped
`GoalLoop` and calls `.run()` on it. This means:

- There is exactly one execution engine to reason about, test, and debug.
- Nesting is free: a specialist can itself delegate further (bounded by its
  own `max_turns`), without any special-casing.
- Swapping "multi-agent mode" on or off is a constructor argument
  (`Orchestrator | None`), not a different code path.

## Why turns are the unit of memory, not messages

Chat-style memory (a transcript of messages) captures *what was said*.
SelfPrompt persists `Turn` objects — observation, critique, action, result —
because that captures *what was decided and why*, which is what a resumed
loop or a future run actually needs. `progress.md` is the human-readable
projection of the same data; `turns.jsonl` is the structured one `FileMemory`
reads back on the next `run()`.

## Why the model's self-critique is a hard requirement, not a suggestion

The JSON contract the loop enforces (see `core/loop.py::_DEFAULT_SYSTEM_PROMPT`)
requires `critique` on every single turn, before the model is allowed to
declare an `action`. Two consequences:

1. A model can't skip straight to `finish` without having gone on record
   about its confidence — `LoopResult.turns[-1].critique.confidence` is
   always available for a caller (or a `StopCondition`) to check.
2. Failures self-document: any turn with `issues` non-empty gets a lesson
   written to `lessons.md` automatically, without the caller having to
   parse free text to find out what went wrong.

## Extending the tool layer safely

`ToolRegistry.call()` is the single choke point for permissions. Tools
never decide for themselves whether they're allowed to run — they only
declare `dangerous: bool`. This means a new dangerous tool is safe by
construction: it inherits whatever `permission_mode` the host configured
(`allow` / `ask` / `deny`) with zero additional code.
