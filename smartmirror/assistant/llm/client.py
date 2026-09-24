"""OpenAI-compatible LLM client.

This module talks to any OpenAI-compatible chat-completions endpoint
(OpenAI itself, a local vLLM/Ollama/llama.cpp server, etc). It must not
import anything from `smartmirror.assistant.rag` -- prompt assembly (mixing
retrieved context into the message list) is the Assistant's job, not the
LLM client's.
"""

from openai import OpenAI


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat-completions API."""

    def __init__(self, api_key, base_url=None, model="gpt-4o-mini"):
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, messages: list[dict], tools=None) -> dict:
        """Run one chat-completion call.

        Args:
            messages: OpenAI-style list of {"role": ..., "content": ...} dicts.
            tools: optional OpenAI-style tool/function definitions to expose
                to the model for function calling.

        Returns:
            A dict with at least a "content" key (the assistant's reply text,
            possibly empty if the model only returned tool calls) and a
            "tool_calls" key (list, empty when none were requested).
        """
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        return {
            "content": choice.content or "",
            "tool_calls": choice.tool_calls or [],
        }
