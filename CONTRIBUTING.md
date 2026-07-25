# Contributing to SelfPrompt

## Setup

```bash
git clone https://github.com/your-org/selfprompt
cd selfprompt
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Ground rules

- **Keep the core dependency-light.** `src/selfprompt/core`, `memory`,
  `tools`, and `agents` should never require anything beyond `pyyaml` and
  the stdlib. Vendor-specific code (Anthropic/OpenAI SDKs, numpy) stays
  behind optional extras and a lazy `import` inside the function that needs
  it, so `pip install selfprompt` alone stays light.
- **No new abstractions without three real call sites.** If you're adding a
  base class, factory, or plugin system, show the three concrete things it
  would serve, or open an issue to discuss first.
- **Every new `Tool` needs a `dangerous` flag decision.** If it can write,
  execute, or send anything, `dangerous = True` and it goes through the
  permission model — no exceptions.
- **New specialist agents are YAML, not code**, unless the routing logic
  genuinely can't be expressed as trigger keywords.

## Tests

- `pytest` must pass with zero network access — use `MockProvider` for
  anything touching `LLMProvider`.
- New `Tool`s need a test exercising both the success and failure path.
- New `MemoryBackend` methods need a round-trip test (`tmp_path` fixture).

## Style

- `ruff check src tests` and `mypy src` should be clean.
- Follow existing patterns: dataclasses over class hierarchies where
  possible, `Protocol`s over ABCs for interfaces, no comments explaining
  *what* code does — only *why*, when it's non-obvious.

## Pull requests

- Keep PRs scoped to one concern. A new tool, a new example, and a docs fix
  are three PRs, not one.
- Describe what you tested manually (a real `selfprompt run` against a real
  provider, if the change touches the loop or a connector) in the PR
  description — CI runs the mock-based suite, not a live model.
