---
name: selfprompt
description: Pursue a goal autonomously via a bounded self-prompting loop with persistent memory and sub-agents, instead of manually chaining prompts one by one. Use when the user says "/goal", "run this autonomously", "keep iterating on this until X", or gives a multi-step task with a clear definition of done.
---

# SelfPrompt

Runs a goal-driven agentic loop using **this Claude Code session as the
model** — no second API key, no separate billing. You (the agent reading
this) act as the loop's brain each turn; `selfprompt` just handles the
bookkeeping (memory, budgets, stop conditions).

## When to use

- The user gives a goal with a checkable definition of done ("until tests
  pass", "until the PR has no review comments", "produce a report on X").
- The user wants iteration to keep happening without re-prompting each step.
- The task benefits from persistent memory across multiple `/selfprompt`
  calls in the same repo (progress and lessons live in
  `.selfprompt/memory/`).

## How to run it (host-driven mode — default, no API key)

1. If `.selfprompt/config.yaml` doesn't exist yet, run `selfprompt init` in
   the project root first.
2. Pick a `goal_id` (slug of the user's goal, e.g. `refactor-payments`).
3. Loop, and **narrate each turn in your visible reply** — don't just run
   these silently and dump a final summary; the user should be able to
   watch the loop think, the same way they'd watch you work normally:

   ```bash
   selfprompt step <goal_id>
   ```

   Do **not** pass `--json` here — the default output is the formatted
   prompt text, meant to be read (and shown). It's either `DONE: <reason>`
   — stop and report — or the goal, available tools, prior memory, and
   recent history, followed by a turn index.

4. If not done: post a short visible line stating what you observed and
   what you're about to do this turn (this is your own `observation` +
   `critique` + planned `action`, in plain language, not the raw JSON).
5. **Perform the action yourself**, using your own Read/Write/Edit/Bash
   tools (normal Claude Code permissions apply — this is safer than
   shelling out, since the user sees your usual tool-approval prompts, not
   a second permission system). Capture what happened as `result` text.
6. Persist the turn:

   ```bash
   selfprompt record-turn <goal_id> --turn-index N --data '{
     "observation": "...", "critique": {"progress_made": true, "confidence": 0.8, "issues": []},
     "action": {"type": "tool_call", "detail": "...", "tool_name": "...", "tool_args": {}},
     "result": "..."
   }'
   ```

   Prints a plain status line (`Turn N recorded. ...`); pass `--json` only
   if you need the structured `{"finished", "aborted", "stop_reason"}`
   form for your own branching logic.

7. If not finished/aborted, go back to step 3. Stop the moment `step`
   reports `DONE`, or `record-turn` reports `FINISHED`/`ABORTED`.
8. Report back to the user: finished or stopped, why, how many turns, and
   the final result. `selfprompt status <goal_id>` shows the full log if
   asked.

Use `action.type: "finish"` only once you've actually verified the goal —
run tests, re-read the file, whatever "done" means here. Use `"abort"` if
you get stuck with no new approach after a few turns; don't loop forever
retrying the same thing.

## Alternative: subprocess mode (separate API key)

If you'd rather have `selfprompt` run unattended as its own process with
its own model call (e.g. for a background/CI job, not an interactive
session), that needs `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set — this is
a second, separately billed model call, not free via this session:

```bash
selfprompt run "<goal>" --provider anthropic --max-turns 20
```

Prefer host-driven mode (above) when you're already in a Claude Code
session — it's free and gives the user their usual permission prompts.

## Multi-agent mode

For `run`, pass `--multi-agent` to route delegated sub-goals to specialist
agents (researcher, coder, reviewer, critic, security) defined in
`.selfprompt/agents/*.yaml`. In host-driven mode, delegation is just
you (the agent) choosing to think as a different specialist persona for
that turn — read `src/selfprompt/agents/defs/*.yaml` in the SelfPrompt
package for the built-in personas' framing if asked to delegate.

## Making `/selfprompt` available in other projects

This file only triggers `/selfprompt` inside repos that have it under their
own `.claude/skills/selfprompt/`. To use it everywhere, install it once at
the user level instead:

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/selfprompt/.claude/skills/selfprompt ~/.claude/skills/
```

Then `pip install git+https://github.com/iamkallolpratim/selfprompt.git` so
the `selfprompt` binary is on `PATH`, and `/selfprompt <goal>` works in any
project's Claude Code session, no per-repo copy needed. `selfprompt init`
still needs to run once per project (writes `.selfprompt/config.yaml` and
`.selfprompt/memory/` there).

## Safety

In host-driven mode, tool execution goes through your normal Claude Code
permissions — nothing extra to configure. In subprocess mode (`run`),
dangerous tool calls (shell, file writes, code exec) are gated by
`permission_mode` in `.selfprompt/config.yaml` (`ask` by default); don't
pass `--yes` unless the user has explicitly asked for unattended execution.
