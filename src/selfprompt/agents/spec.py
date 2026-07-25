"""Agent specifications: the whole point is that defining a specialist should
take a YAML file, not a subclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AgentSpec:
    name: str
    role: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)  # keywords that route to this agent
    max_turns: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AgentSpec:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        return cls(
            name=data["name"],
            role=data.get("role", data["name"]),
            system_prompt=data["system_prompt"].strip(),
            tools=data.get("tools", []),
            triggers=data.get("triggers", []),
            max_turns=data.get("max_turns", 10),
            metadata=data.get("metadata", {}),
        )

    def matches(self, text: str) -> int:
        """Cheap relevance score for routing: count of trigger keywords found."""
        lowered = text.lower()
        return sum(1 for trig in self.triggers if trig.lower() in lowered)
