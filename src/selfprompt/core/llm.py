"""Pluggable LLM provider interface.

SelfPrompt does not hard-depend on any single model vendor. The loop only
needs something that turns a prompt into text and reports usage. Anything
that satisfies `LLMProvider` -- the Anthropic SDK, the OpenAI SDK, a local
model, or the very host agent SelfPrompt is running inside of (Claude Code,
Codex) -- can drive the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract the loop needs from a model backend."""

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        """Return a completion for `prompt`. Must be synchronous."""
        ...


class CallbackProvider:
    """Wraps a plain `def fn(prompt: str, system: str | None) -> str` callable.

    This is the escape hatch for the "host agent as the LLM" case: when
    SelfPrompt runs as a Claude Code skill or Codex connector, the host
    already has a model loaded and billed -- SelfPrompt should not spin up a
    second one. Wrap whatever the host exposes in a callback and hand it to
    the loop.
    """

    def __init__(self, fn: Any) -> None:
        self._fn = fn

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        text = self._fn(prompt, system)
        return LLMResponse(text=text)


class AnthropicProvider:
    """Thin wrapper around the Anthropic SDK. Requires `pip install selfprompt[anthropic]`."""

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None,
                 max_tokens: int = 4096) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "AnthropicProvider requires the 'anthropic' package: "
                "pip install selfprompt[anthropic]"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        text = "".join(block.text for block in msg.content if block.type == "text")
        return LLMResponse(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            raw=msg.model_dump() if hasattr(msg, "model_dump") else {},
        )


class OpenAIProvider:
    """Thin wrapper around the OpenAI SDK. Requires `pip install selfprompt[openai]`."""

    def __init__(self, model: str = "gpt-5", api_key: str | None = None) -> None:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "OpenAIProvider requires the 'openai' package: pip install selfprompt[openai]"
            ) from exc
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(model=self._model, messages=messages)
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


class MockProvider:
    """Deterministic, offline provider for tests and dry runs.

    Takes a list of canned responses (or a callable) and returns them in
    order. Never makes a network call.
    """

    def __init__(self, responses: list[str] | Any) -> None:
        self._responses = responses
        self._index = 0

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        if callable(self._responses):
            text = self._responses(prompt, system)
        else:
            text = self._responses[min(self._index, len(self._responses) - 1)]
            self._index += 1
        return LLMResponse(text=text, input_tokens=len(prompt.split()), output_tokens=len(text.split()))
