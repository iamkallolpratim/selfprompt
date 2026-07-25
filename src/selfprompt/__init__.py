"""SelfPrompt: a framework-agnostic self-prompting / agentic loop engine."""

from selfprompt.core.llm import LLMProvider, LLMResponse
from selfprompt.core.loop import GoalLoop
from selfprompt.core.state import Budget, LoopResult, StopCondition

__all__ = [
    "Budget",
    "GoalLoop",
    "LLMProvider",
    "LLMResponse",
    "LoopResult",
    "StopCondition",
]

__version__ = "0.1.0"
