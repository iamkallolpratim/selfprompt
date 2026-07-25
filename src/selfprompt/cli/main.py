"""The `selfprompt` CLI: `init`, `run`, `status`.

Deliberately argparse-based (stdlib only) so the CLI never gains a
dependency the core engine doesn't already need.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from selfprompt.agents.orchestrator import Orchestrator
from selfprompt.agents.registry import load_all_agents
from selfprompt.cli.config import DEFAULT_CONFIG_PATH, ProjectConfig
from selfprompt.core.loop import GoalLoop
from selfprompt.core.state import Budget
from selfprompt.memory.file_backend import FileMemory
from selfprompt.tools.code_exec import PythonExecTool
from selfprompt.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from selfprompt.tools.git import GitTool
from selfprompt.tools.registry import Permission, ToolRegistry
from selfprompt.tools.shell import ShellTool


def _default_tools() -> list:
    return [ReadFileTool(), WriteFileTool(), ListDirTool(), ShellTool(), GitTool(), PythonExecTool()]


def _build_llm(config: ProjectConfig):
    if config.provider == "mock":
        from selfprompt.core.llm import MockProvider

        mock_decision = (
            '{"observation": "no-op mock turn", '
            '"critique": {"progress_made": true, "confidence": 0.5, "issues": []}, '
            '"action": {"type": "finish", "detail": "mock provider always finishes immediately"}}'
        )
        return MockProvider([mock_decision])
    if config.provider == "anthropic":
        from selfprompt.core.llm import AnthropicProvider

        return AnthropicProvider(model=config.model)
    if config.provider == "openai":
        from selfprompt.core.llm import OpenAIProvider

        return OpenAIProvider(model=config.model)
    raise SystemExit(f"unknown provider: {config.provider}")


def _ask_permission(name: str, args: dict) -> bool:
    preview = ", ".join(f"{k}={v!r}" for k, v in args.items())
    answer = input(f"allow tool '{name}' ({preview})? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def cmd_init(args: argparse.Namespace) -> None:
    config = ProjectConfig()
    config.write_default(DEFAULT_CONFIG_PATH)
    Path(".selfprompt/agents").mkdir(parents=True, exist_ok=True)
    Path(".selfprompt/memory").mkdir(parents=True, exist_ok=True)
    print(f"Initialized SelfPrompt project at {DEFAULT_CONFIG_PATH}")
    print("Next: selfprompt run \"your goal here\"")


def cmd_run(args: argparse.Namespace) -> None:
    config = ProjectConfig.load()
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.max_turns:
        config.max_turns = args.max_turns

    llm = _build_llm(config)
    permission_mode = Permission.ALLOW if args.yes else Permission(config.permission_mode)
    tools = ToolRegistry(
        _default_tools(), permission_mode=permission_mode, on_permission_request=_ask_permission
    )
    memory = FileMemory(config.memory_root)

    orchestrator = None
    if args.multi_agent:
        agents = load_all_agents(config.agents_dir)
        orchestrator = Orchestrator(agents, llm=llm, tool_registry=tools, memory=memory)

    def on_message(text: str) -> None:
        print(f"  > {text}")

    loop = GoalLoop(
        args.goal,
        llm=llm,
        tools=tools,
        memory=memory,
        orchestrator=orchestrator,
        budget=Budget(
            max_turns=config.max_turns, max_tokens=config.max_tokens, max_cost_usd=config.max_cost_usd
        ),
        goal_id=args.goal_id,
        on_message=on_message,
    )

    if not args.json:
        print(f"Goal: {args.goal}")
        print(f"Goal ID: {loop.goal_id}  (resume with --goal-id {loop.goal_id})")
    result = loop.run()

    if args.json:
        import json as _json

        print(_json.dumps(result.to_dict()))
    else:
        print(f"\n{'FINISHED' if result.finished else 'STOPPED'}: {result.stop_reason}")
        print(f"Turns: {result.turn_count}  Tokens: {result.total_tokens}  Cost: ${result.total_cost_usd:.4f}")
    sys.exit(0 if result.finished else 1)


def _step_loop(config: ProjectConfig, goal_id: str, max_turns: int | None) -> GoalLoop:
    from selfprompt.core.llm import NullProvider

    return GoalLoop(
        goal_id,
        llm=NullProvider(),
        tools=ToolRegistry(_default_tools()),
        memory=FileMemory(config.memory_root),
        budget=Budget(max_turns=max_turns or config.max_turns),
        goal_id=goal_id,
    )


def cmd_step(args: argparse.Namespace) -> None:
    """Host-driven mode: return the next prompt without calling an LLM.

    For a caller that IS the model (e.g. Claude Code answering
    `/selfprompt` on the user's own subscription instead of a second
    billed API key) -- see `record-turn` for the other half.
    """
    import json as _json

    config = ProjectConfig.load()
    loop = _step_loop(config, args.goal_id, args.max_turns)
    print(_json.dumps(loop.next_step()))


def cmd_record_turn(args: argparse.Namespace) -> None:
    import json as _json

    config = ProjectConfig.load()
    loop = _step_loop(config, args.goal_id, args.max_turns)
    data = _json.loads(args.data)
    result = loop.record_step(
        turn_index=args.turn_index,
        observation=data.get("observation", ""),
        critique=data.get("critique", {}),
        action=data["action"],
        result=data.get("result", ""),
    )
    print(_json.dumps(result))


def cmd_status(args: argparse.Namespace) -> None:
    config = ProjectConfig.load()
    root = Path(config.memory_root)
    if args.goal_id:
        goal_dir = root / args.goal_id
        progress = goal_dir / "progress.md"
        lessons = goal_dir / "lessons.md"
        if not goal_dir.exists():
            print(f"no memory found for goal_id '{args.goal_id}'")
            return
        if progress.exists():
            print(progress.read_text(encoding="utf-8"))
        if lessons.exists():
            print(lessons.read_text(encoding="utf-8"))
        return

    if not root.exists():
        print("no goals recorded yet")
        return
    for goal_dir in sorted(root.iterdir()):
        if not goal_dir.is_dir():
            continue
        turns_file = goal_dir / "turns.jsonl"
        n_turns = sum(1 for _ in turns_file.open()) if turns_file.exists() else 0
        print(f"- {goal_dir.name}  ({n_turns} turns recorded)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selfprompt", description="Self-prompting agentic loop engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a SelfPrompt project in the current directory")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Run a goal-driven loop")
    p_run.add_argument("goal", help="The goal to pursue")
    p_run.add_argument("--goal-id", default=None, help="Resume/persist under this goal id")
    p_run.add_argument("--provider", default=None, choices=["anthropic", "openai", "mock"])
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--max-turns", type=int, default=None)
    p_run.add_argument("--multi-agent", action="store_true", help="Enable orchestrator + specialists")
    p_run.add_argument("--yes", action="store_true", help="Auto-approve dangerous tool calls")
    p_run.add_argument("--json", action="store_true", help="Print machine-readable JSON result only")
    p_run.set_defaults(func=cmd_run)

    p_step = sub.add_parser(
        "step",
        help="Host-driven mode: return the next prompt without calling an LLM (see 'record-turn')",
    )
    p_step.add_argument("goal_id", help="Goal id to advance (matches --goal-id used elsewhere)")
    p_step.add_argument("--max-turns", type=int, default=None)
    p_step.set_defaults(func=cmd_step)

    p_record = sub.add_parser(
        "record-turn",
        help="Host-driven mode: persist a turn decided externally (companion to 'step')",
    )
    p_record.add_argument("goal_id")
    p_record.add_argument("--turn-index", type=int, required=True)
    p_record.add_argument(
        "--data",
        required=True,
        help='JSON: {"observation": "...", "critique": {...}, "action": {...}, "result": "..."}',
    )
    p_record.add_argument("--max-turns", type=int, default=None)
    p_record.set_defaults(func=cmd_record_turn)

    p_status = sub.add_parser("status", help="Show progress for a goal (or list all goals)")
    p_status.add_argument("goal_id", nargs="?", default=None)
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
