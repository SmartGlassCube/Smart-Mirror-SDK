from pathlib import Path
from unittest.mock import MagicMock

import pytest

from smartmirror.assistant.rag import Embedder

SEED_CORPUS = Path(__file__).resolve().parents[1] / "rag" / "seed_corpus"


@pytest.fixture(scope="session")
def embedder():
    """Loading the sentence-transformers model is slow -- share it across tests."""
    return Embedder()


@pytest.fixture
def seed_corpus_path():
    return str(SEED_CORPUS)


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
