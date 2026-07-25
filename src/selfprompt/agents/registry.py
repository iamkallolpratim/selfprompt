"""Loads the built-in specialist agent defs shipped with the package, and
lets users layer their own YAML/Markdown defs on top from a directory.
"""

from __future__ import annotations

from pathlib import Path

from selfprompt.agents.spec import AgentSpec

_BUILTIN_DIR = Path(__file__).parent / "defs"


def load_builtin_agents() -> dict[str, AgentSpec]:
    agents: dict[str, AgentSpec] = {}
    for path in sorted(_BUILTIN_DIR.glob("*.yaml")):
        spec = AgentSpec.from_yaml(path)
        agents[spec.name] = spec
    return agents


def load_agents_from_dir(directory: str | Path) -> dict[str, AgentSpec]:
    """Load user-defined agents from a directory of `*.yaml` files.

    User agents with the same `name` as a built-in override it, so a project
    can customize e.g. `coder` without forking the package.
    """
    agents: dict[str, AgentSpec] = {}
    d = Path(directory)
    if not d.exists():
        return agents
    for path in sorted(d.glob("*.yaml")):
        spec = AgentSpec.from_yaml(path)
        agents[spec.name] = spec
    return agents


def load_all_agents(user_dir: str | Path | None = None) -> dict[str, AgentSpec]:
    agents = load_builtin_agents()
    if user_dir is not None:
        agents.update(load_agents_from_dir(user_dir))
    return agents
