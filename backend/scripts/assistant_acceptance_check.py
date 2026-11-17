#!/usr/bin/env python3
"""Phase 1 acceptance check for glasscube.assistant.

Runs the whole walking skeleton against a real LLM backend: embeds and
indexes the seed corpus into local on-disk Qdrant, retrieves context for a
question the seed corpus can answer, and prints the model's grounded reply.

Requires a real LLM endpoint -- this script makes an actual network call
and is not part of the pytest suite (which uses a fake in-memory LLMBackend
so it can run without credentials or a live server).

Backend is constructed explicitly, same as Assistant now expects:

    Usage (OpenAI-compatible -- OpenAI itself, Ollama, OpenRouter, vLLM, ...):
        export GLASSCUBE_LLM_API_KEY=sk-...          # any non-empty string for Ollama
        export GLASSCUBE_LLM_BASE_URL=http://localhost:11434/v1   # optional
        export GLASSCUBE_LLM_MODEL=qwen2.5:0.5b       # optional
        python scripts/assistant_acceptance_check.py

    Usage (Anthropic):
        export GLASSCUBE_LLM_PROVIDER=anthropic
        export GLASSCUBE_LLM_API_KEY=sk-ant-...
        export GLASSCUBE_LLM_MODEL=claude-sonnet-5    # optional
        python scripts/assistant_acceptance_check.py
"""

import os
import sys

from glasscube.assistant import Assistant
from glasscube.assistant.llm import AnthropicBackend, OpenAICompatBackend
from glasscube.assistant.rag import SEED_CORPUS_DIR as SEED_CORPUS


def build_backend():
    api_key = os.getenv("GLASSCUBE_LLM_API_KEY")
    if not api_key:
        print("Set GLASSCUBE_LLM_API_KEY to a real API key before running this check.", file=sys.stderr)
        return None

    provider = os.getenv("GLASSCUBE_LLM_PROVIDER", "openai_compat")
    if provider == "anthropic":
        return AnthropicBackend(
            api_key=api_key,
            model=os.getenv("GLASSCUBE_LLM_MODEL", "claude-sonnet-5"),
        )
    return OpenAICompatBackend(
        api_key=api_key,
        base_url=os.getenv("GLASSCUBE_LLM_BASE_URL"),
        model=os.getenv("GLASSCUBE_LLM_MODEL", "gpt-4o-mini"),
    )


def main():
    backend = build_backend()
    if backend is None:
        return 1

    a = Assistant(llm=backend)
    a.add_documents(str(SEED_CORPUS))

    question = "What is IEEE INSAT?"
    answer = a.chat(question)

    print(f"Q: {question}")
    print(f"A: {answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
