"""LLMBackend for the Anthropic Messages API.

Must not import anything from `smartmirror.assistant.rag`.
"""

from ..base import LLMBackend

DEFAULT_MAX_TOKENS = 1024


class AnthropicBackend(LLMBackend):
    """Chat-completions backend for Claude models via the Anthropic SDK."""

    def __init__(self, api_key, model="claude-sonnet-5", max_tokens=DEFAULT_MAX_TOKENS):
        from anthropic import Anthropic

        self.model = model
        self.max_tokens = max_tokens
        self._client = Anthropic(api_key=api_key)

    def complete(self, messages: list[dict], tools=None) -> str:
        system_prompt, conversation = self._split_system(messages)

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": conversation,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            # Anthropic's tool schema (input_schema) differs from OpenAI's
            # (parameters) -- callers passing OpenAI-style tool specs here
            # will need translation once ToolManager grows real tool specs.
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)
        return "".join(block.text for block in response.content if block.type == "text")

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
        """Anthropic takes the system prompt as a top-level param, not a message."""
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        conversation = [m for m in messages if m["role"] != "system"]
        return "\n\n".join(system_parts), conversation
