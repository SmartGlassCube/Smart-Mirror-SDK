#!/usr/bin/env python3
"""Phase 1 acceptance check for smartmirror.assistant.

Runs the whole walking skeleton against a real, OpenAI-compatible LLM
endpoint: embeds and indexes the seed corpus into local on-disk Qdrant,
retrieves context for a question the seed corpus can answer, and prints
the model's grounded reply.

Requires a real LLM endpoint -- this script makes an actual network call
and is not part of the pytest suite (which mocks the LLM call so it can
run without credentials).

Usage:
    export SMARTMIRROR_LLM_API_KEY=sk-...
    # Optional: point at any OpenAI-compatible endpoint (Ollama, vLLM, etc).
    export SMARTMIRROR_LLM_BASE_URL=https://api.openai.com/v1
    export SMARTMIRROR_LLM_MODEL=gpt-4o-mini
    python scripts/assistant_acceptance_check.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartmirror.assistant import Assistant

SEED_CORPUS = Path(__file__).resolve().parents[1] / "smartmirror" / "assistant" / "rag" / "seed_corpus"


def main():
    api_key = os.getenv("SMARTMIRROR_LLM_API_KEY")
    if not api_key:
        print("Set SMARTMIRROR_LLM_API_KEY to a real API key before running this check.", file=sys.stderr)
        return 1

    a = Assistant(
        api_key=api_key,
        url=os.getenv("SMARTMIRROR_LLM_BASE_URL"),
        model=os.getenv("SMARTMIRROR_LLM_MODEL", "gpt-4o-mini"),
    )
    a.add_documents(str(SEED_CORPUS))

    question = "What is IEEE INSAT?"
    answer = a.chat(question)

    print(f"Q: {question}")
    print(f"A: {answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
