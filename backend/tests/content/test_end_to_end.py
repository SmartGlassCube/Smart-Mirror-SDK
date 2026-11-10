"""End-to-end: a real Assistant, backed by the Mongo-derived content, answers a question.

Uses whichever OpenAI-compatible endpoint examples/mvp.py defaults to (local
Ollama, SMARTMIRROR_LLM_* env vars to override). If nothing answers there,
falls back to asserting retrieval + prompt-block assembly only, and skips
the actual chat() call with a clear reason.
"""
import os

import httpx
import pytest

from smartmirror.assistant import Assistant
from smartmirror.assistant.llm import OpenAICompatBackend

from .conftest import make_about, make_event, requires_mongo

pytestmark = requires_mongo

LLM_BASE_URL = os.getenv("SMARTMIRROR_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("SMARTMIRROR_LLM_MODEL", "qwen2.5:0.5b")
LLM_API_KEY = os.getenv("SMARTMIRROR_LLM_API_KEY", "ollama")


def _llm_reachable() -> bool:
    try:
        resp = httpx.get(f"{LLM_BASE_URL}/models", timeout=2)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def test_assistant_answers_next_event_question(mongo_db, content_sync):
    make_event(mongo_db, title="Robotics Expo 2026", description="A showcase of student robotics projects.")
    make_about(mongo_db)
    content_sync.reconcile()

    if not _llm_reachable():
        # No LLM available in this environment -- verify retrieval + prompt
        # assembly instead, which is what an LLM would actually see.
        pytest.skip(f"no LLM reachable at {LLM_BASE_URL} -- checking retrieval/prompt assembly only below")

    backend = OpenAICompatBackend(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, model=LLM_MODEL)
    assistant = Assistant(
        llm=backend, store=content_sync.indexer.store, extra_context=content_sync.prompt_block,
    )
    assistant.retriever.embedder = content_sync.indexer.embedder

    answer = assistant.chat("What is the next event?")
    assert "Robotics Expo 2026" in answer, f"expected the seeded event title in the answer, got: {answer!r}"


def test_retrieval_and_prompt_block_contain_the_answer_regardless_of_llm(mongo_db, content_sync):
    """Always runs: the ground truth an LLM would be given, independent of whether one is reachable."""
    make_event(mongo_db, title="Robotics Expo 2026", description="A showcase of student robotics projects.")
    make_about(mongo_db)
    content_sync.reconcile()

    block = content_sync.prompt_block()
    assert "Robotics Expo 2026" in block

    from smartmirror.assistant.rag import Retriever
    retriever = Retriever(store=content_sync.indexer.store, embedder=content_sync.indexer.embedder)
    chunks = retriever.retrieve("What is the next event?")
    assert any("Robotics Expo 2026" in chunk for chunk in chunks)
