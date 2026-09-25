"""LLMBackend for any OpenAI-compatible /v1/chat/completions endpoint.

Covers OpenAI itself, and any self-hosted or third-party server that speaks
the same API -- Ollama, OpenRouter, vLLM, llama.cpp's server, etc.

Must not import anything from `smartmirror.assistant.rag`.
"""

from openai import OpenAI

from ..base import LLMBackend


class OpenAICompatBackend(LLMBackend):
    """Chat-completions backend for OpenAI and OpenAI-compatible servers."""

    def __init__(self, api_key, base_url=None, model="gpt-4o-mini"):
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, messages: list[dict], tools=None) -> str:
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
