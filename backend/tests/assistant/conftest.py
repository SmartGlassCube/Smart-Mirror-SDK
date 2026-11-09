from unittest.mock import MagicMock

import pytest

from smartmirror.assistant.llm import LLMBackend
from smartmirror.assistant.rag import SEED_CORPUS_DIR, Embedder


@pytest.fixture(scope="session")
def embedder():
    """Loading the sentence-transformers model is slow -- share it across tests."""
    return Embedder()


@pytest.fixture
def seed_corpus_path():
    return str(SEED_CORPUS_DIR)


def make_fake_openai_response(content: str):
    """Build a MagicMock shaped like an OpenAI chat.completions.create() response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


@pytest.fixture
def fake_llm_response():
    return make_fake_openai_response


class FakeLLMBackend(LLMBackend):
    """An in-memory LLMBackend for testing Assistant without any network I/O."""

    def __init__(self, reply: str = "stub reply"):
        self.reply = reply
        self.calls: list[dict] = []

    def complete(self, messages, tools=None) -> str:
        self.calls.append({"messages": messages, "tools": tools})
        return self.reply


@pytest.fixture
def fake_backend():
    return FakeLLMBackend
