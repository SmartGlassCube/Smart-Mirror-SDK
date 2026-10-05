"""Abstract interface every LLM backend implements.

Must not import anything from `smartmirror.assistant.rag`.
"""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """A pluggable chat-completion backend (OpenAI-compatible, Anthropic, ...)."""

    @abstractmethod
    def complete(self, messages: list[dict], tools=None) -> str:
        """Run one chat-completion call and return the assistant's reply text.

        Args:
            messages: OpenAI-style list of {"role": ..., "content": ...} dicts.
            tools: optional tool/function definitions to expose to the model.
                Backends that don't support function calling yet may ignore this.
        """
        raise NotImplementedError
