---
name: selfprompt
description: Pursue a goal autonomously via a bounded self-prompting loop with persistent memory and sub-agents, instead of manually chaining prompts one by one. Use when the user says "/goal", "run this autonomously", "keep iterating on this until X", or gives a multi-step task with a clear definition of done.
---

# SelfPrompt

Runs `selfprompt` as a goal-driven agentic loop, using the current Claude
Code session as the model backend (no second API key needed).

## When to use

- The user gives a goal with a checkable definition of done ("until tests
  pass", "until the PR has no review comments", "produce a report on X").
- The user wants iteration to keep happening without re-prompting each step.
- The task benefits from persistent memory across multiple `/goal` calls in
  the same repo (progress and lessons live in `.selfprompt/memory/`).

## How to run it

1. If `.selfprompt/config.yaml` doesn't exist yet, run `selfprompt init` in
   the project root first.
2. Run the goal:

   ```bash
   selfprompt run "<the user's goal>" --provider mock --max-turns 20
   ```

   Replace `--provider mock` with whatever the project's
   `.selfprompt/config.yaml` specifies once real model wiring is set up (see
   `selfprompt/connectors/claude_code.py` for wiring the loop's model calls
   directly through this session instead of a second API key).

3. Report back to the user: whether it finished or stopped, the stop
   reason, turn count, and the last action's result. Use
   `selfprompt status <goal-id>` to show the full progress log if asked.

## Multi-agent mode

Pass `--multi-agent` to route delegated sub-goals to specialist agents
(researcher, coder, reviewer, critic, security) defined in
`.selfprompt/agents/*.yaml`. See `src/selfprompt/agents/defs/` in the
SelfPrompt package for the built-in specialist definitions and format.

## Safety

Dangerous tool calls (shell, file writes, code exec) are gated by the
permission model in `.selfprompt/config.yaml` (`permission_mode: ask` by
default). Do not pass `--yes` unless the user has explicitly asked for
unattended execution.
