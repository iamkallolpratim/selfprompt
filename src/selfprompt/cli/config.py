"""Project config: `.selfprompt/config.yaml`.

Kept as one small, flat YAML file on purpose -- `selfprompt init` writes
sane defaults and most projects never need to touch it beyond swapping the
provider/model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(".selfprompt/config.yaml")

_DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "budget": {"max_turns": 25, "max_tokens": None, "max_cost_usd": None},
    "permission_mode": "ask",
    "memory_root": ".selfprompt/memory",
    "agents_dir": ".selfprompt/agents",
}


@dataclass(slots=True)
class ProjectConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    max_turns: int = 25
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    permission_mode: str = "ask"
    memory_root: str = ".selfprompt/memory"
    agents_dir: str = ".selfprompt/agents"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> ProjectConfig:
        p = Path(path)
        data = dict(_DEFAULT_CONFIG)
        if p.exists():
            loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            data.update(loaded)
        budget = data.get("budget", {})
        known = {"provider", "model", "budget", "permission_mode", "memory_root", "agents_dir"}
        return cls(
            provider=data.get("provider", "anthropic"),
            model=data.get("model", "claude-sonnet-5"),
            max_turns=budget.get("max_turns", 25),
            max_tokens=budget.get("max_tokens"),
            max_cost_usd=budget.get("max_cost_usd"),
            permission_mode=data.get("permission_mode", "ask"),
            memory_root=data.get("memory_root", ".selfprompt/memory"),
            agents_dir=data.get("agents_dir", ".selfprompt/agents"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def write_default(self, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(_DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")
