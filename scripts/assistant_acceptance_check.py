#!/usr/bin/env python3
"""Phase 1 acceptance check for smartmirror.assistant.

Runs the whole walking skeleton against a real LLM backend: embeds and
indexes the seed corpus into local on-disk Qdrant, retrieves context for a
question the seed corpus can answer, and prints the model's grounded reply.

Requires a real LLM endpoint -- this script makes an actual network call
and is not part of the pytest suite (which uses a fake in-memory LLMBackend
so it can run without credentials or a live server).

Backend is constructed explicitly, same as Assistant now expects:

    Usage (OpenAI-compatible -- OpenAI itself, Ollama, OpenRouter, vLLM, ...):
        export SMARTMIRROR_LLM_API_KEY=sk-...          # any non-empty string for Ollama
        export SMARTMIRROR_LLM_BASE_URL=http://localhost:11434/v1   # optional
        export SMARTMIRROR_LLM_MODEL=qwen2.5:0.5b       # optional
        python scripts/assistant_acceptance_check.py

    Usage (Anthropic):
        export SMARTMIRROR_LLM_PROVIDER=anthropic
        export SMARTMIRROR_LLM_API_KEY=sk-ant-...
        export SMARTMIRROR_LLM_MODEL=claude-sonnet-5    # optional
        python scripts/assistant_acceptance_check.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartmirror.assistant import Assistant
from smartmirror.assistant.llm import AnthropicBackend, OpenAICompatBackend

SEED_CORPUS = Path(__file__).resolve().parents[1] / "smartmirror" / "assistant" / "rag" / "seed_corpus"


def build_backend():
    api_key = os.getenv("SMARTMIRROR_LLM_API_KEY")
    if not api_key:
        print("Set SMARTMIRROR_LLM_API_KEY to a real API key before running this check.", file=sys.stderr)
        return None

    provider = os.getenv("SMARTMIRROR_LLM_PROVIDER", "openai_compat")
    if provider == "anthropic":
        return AnthropicBackend(
            api_key=api_key,
            model=os.getenv("SMARTMIRROR_LLM_MODEL", "claude-sonnet-5"),
        )
    return OpenAICompatBackend(
        api_key=api_key,
        base_url=os.getenv("SMARTMIRROR_LLM_BASE_URL"),
        model=os.getenv("SMARTMIRROR_LLM_MODEL", "gpt-4o-mini"),
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
