"""Assistant orchestration tests.

The LLM backend is a fake, in-memory LLMBackend -- no network/API key and no
mocking of any specific provider SDK needed to run the suite. Everything
else -- chunking, embedding, indexing into a real local Qdrant, and
retrieval -- runs for real. This is the phase 1 acceptance check in
CI-friendly form; `scripts/assistant_acceptance_check.py` runs the same
flow against a real LLM endpoint when you have credentials.
"""

import functools

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


def test_chat_grounds_answer_in_retrieved_context(isolated_vector_store, seed_corpus_path, fake_backend):
    backend = fake_backend(reply="IEEE INSAT is the IEEE student branch at INSAT in Tunis.")

    a = Assistant(llm=backend, documents=seed_corpus_path)
    answer = a.chat("What is IEEE INSAT?")

    assert answer == "IEEE INSAT is the IEEE student branch at INSAT in Tunis."

    sent_messages = backend.calls[-1]["messages"]
    assert sent_messages[0]["role"] == "system"
    user_message = sent_messages[-1]["content"]
    assert "Context:" in user_message
    assert "IEEE INSAT" in user_message
    assert "What is IEEE INSAT?" in user_message


def test_chat_updates_history(isolated_vector_store, seed_corpus_path, fake_backend):
    backend = fake_backend(reply="some answer")

    a = Assistant(llm=backend, documents=seed_corpus_path)
    a.chat("What is IEEE INSAT?")

    assert a.history == [
        {"role": "user", "content": "What is IEEE INSAT?"},
        {"role": "assistant", "content": "some answer"},
    ]

    a.reset_history()
    assert a.history == []


def test_add_documents_makes_them_retrievable(isolated_vector_store, tmp_path, fake_backend):
    doc = tmp_path / "extra.txt"
    doc.write_text("The Smart Mirror SDK ships a gesture-driven UI.", encoding="utf-8")
    backend = fake_backend(reply="It ships a gesture-driven UI.")

    a = Assistant(llm=backend)
    a.add_documents(str(doc))
    a.chat("What does the Smart Mirror SDK ship?")

    user_message = backend.calls[-1]["messages"][-1]["content"]
    assert "gesture-driven UI" in user_message


def test_voice_chat_is_not_implemented_yet(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend())
    with pytest.raises(NotImplementedError):
        a.voice_chat()


def test_stt_and_tts_are_stubs_when_enabled(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True, tts=True)

    assert a.stt is not None
    with pytest.raises(NotImplementedError):
        a.stt.listen()

    assert a.tts.enabled is True
    with pytest.raises(NotImplementedError):
        a.tts.speak("hello")


def test_tts_disabled_by_default_is_a_silent_no_op(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend())

    assert a.tts.enabled is False
    assert a.stt is None
    a.tts.speak("hello")  # must not raise


def test_backward_compat_api_key_kwarg_still_builds_an_openai_compat_backend(isolated_vector_store):
    from smartmirror.assistant.llm import OpenAICompatBackend

    a = Assistant(api_key="sk-test", url="http://localhost:11434/v1", model="qwen2.5:0.5b")

    assert isinstance(a.llm.backend, OpenAICompatBackend)


def test_requires_llm_or_api_key(isolated_vector_store):
    with pytest.raises(ValueError):
        Assistant()
