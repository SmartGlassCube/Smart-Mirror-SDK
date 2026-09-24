"""Assistant orchestration tests.

The LLM call is mocked (no network/API key needed to run the suite), but
everything else -- chunking, embedding, indexing into a real local Qdrant,
and retrieval -- runs for real. This is the phase 1 acceptance check in
CI-friendly form; `scripts/assistant_acceptance_check.py` runs the same
flow against a real LLM endpoint when you have credentials.
"""

import functools
from unittest.mock import patch

import pytest

from smartmirror.assistant import assistant as assistant_module
from smartmirror.assistant import Assistant
from smartmirror.assistant.rag import VectorStore


@pytest.fixture
def isolated_vector_store(tmp_path, monkeypatch):
    """Point Assistant's internal VectorStore at a throwaway on-disk path."""
    monkeypatch.setattr(
        assistant_module,
        "VectorStore",
        functools.partial(VectorStore, path=str(tmp_path / "qdrant")),
    )


def test_chat_grounds_answer_in_retrieved_context(isolated_vector_store, seed_corpus_path, fake_llm_response):
    fake_response = fake_llm_response("IEEE INSAT is the IEEE student branch at INSAT in Tunis.")

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ) as mock_create:
        a = Assistant(api_key="sk-test", documents=seed_corpus_path)
        answer = a.chat("What is IEEE INSAT?")

    assert answer == "IEEE INSAT is the IEEE student branch at INSAT in Tunis."

    sent_messages = mock_create.call_args.kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    user_message = sent_messages[-1]["content"]
    assert "Context:" in user_message
    assert "IEEE INSAT" in user_message
    assert "What is IEEE INSAT?" in user_message


def test_chat_updates_history(isolated_vector_store, seed_corpus_path, fake_llm_response):
    fake_response = fake_llm_response("some answer")

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ):
        a = Assistant(api_key="sk-test", documents=seed_corpus_path)
        a.chat("What is IEEE INSAT?")

    assert a.history == [
        {"role": "user", "content": "What is IEEE INSAT?"},
        {"role": "assistant", "content": "some answer"},
    ]

    a.reset_history()
    assert a.history == []


def test_add_documents_makes_them_retrievable(isolated_vector_store, tmp_path, fake_llm_response):
    doc = tmp_path / "extra.txt"
    doc.write_text("The Smart Mirror SDK ships a gesture-driven UI.", encoding="utf-8")
    fake_response = fake_llm_response("It ships a gesture-driven UI.")

    with patch(
        "openai.resources.chat.completions.completions.Completions.create",
        return_value=fake_response,
    ) as mock_create:
        a = Assistant(api_key="sk-test")
        a.add_documents(str(doc))
        a.chat("What does the Smart Mirror SDK ship?")

    user_message = mock_create.call_args.kwargs["messages"][-1]["content"]
    assert "gesture-driven UI" in user_message


def test_voice_chat_is_not_implemented_yet(isolated_vector_store):
    a = Assistant(api_key="sk-test")
    with pytest.raises(NotImplementedError):
        a.voice_chat()


def test_stt_and_tts_are_stubs_when_enabled(isolated_vector_store):
    a = Assistant(api_key="sk-test", stt=True, tts=True)

    assert a.stt is not None
    with pytest.raises(NotImplementedError):
        a.stt.listen()

    assert a.tts.enabled is True
    with pytest.raises(NotImplementedError):
        a.tts.speak("hello")


def test_tts_disabled_by_default_is_a_silent_no_op(isolated_vector_store):
    a = Assistant(api_key="sk-test")

    assert a.tts.enabled is False
    assert a.stt is None
    a.tts.speak("hello")  # must not raise
