"""Backend-agnostic entry point used by Assistant.

LLMClient itself does nothing but delegate -- it holds no provider-specific
logic. Swapping providers (OpenAI-compatible, Anthropic, ...) means passing
a different LLMBackend, not touching this file or the Assistant.

Must not import anything from `smartmirror.assistant.rag`.
"""

from .base import LLMBackend


class LLMClient:
    """Thin wrapper that delegates chat completions to an LLMBackend."""

    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def complete(self, messages: list[dict], tools=None) -> str:
        return self.backend.complete(messages, tools=tools)
