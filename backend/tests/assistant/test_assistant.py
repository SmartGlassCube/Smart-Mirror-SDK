"""Assistant orchestration tests.

The LLM backend is a fake, in-memory LLMBackend -- no network/API key and no
mocking of any specific provider SDK needed to run the suite. Everything
else -- chunking, embedding, indexing into a real local Qdrant, and
retrieval -- runs for real. This is the phase 1 acceptance check in
CI-friendly form; `scripts/assistant_acceptance_check.py` runs the same
flow against a real LLM endpoint when you have credentials.
"""

import asyncio
import functools
import threading
import time
from unittest.mock import MagicMock

import pytest

from smartmirror.assistant import assistant as assistant_module
from smartmirror.assistant import Assistant
from smartmirror.assistant.llm import LLMBackend
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


class _ScriptedBackend(LLMBackend):
    """Returns `replies` in order, one per call: the answer, then the shortened answer."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, messages, tools=None):
        self.calls.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


LONG_ANSWER = " ".join(["word"] * 50) + "."


def test_short_answer_is_kept_as_is(isolated_vector_store):
    backend = _ScriptedBackend("The workshop is at 14:00.")
    a = Assistant(llm=backend, max_answer_words=10)

    assert a.chat("When is the workshop?") == "The workshop is at 14:00."
    assert len(backend.calls) == 1


def test_long_answer_is_reformulated_shorter(isolated_vector_store):
    backend = _ScriptedBackend(LONG_ANSWER, "The workshop is at 14:00.")
    a = Assistant(llm=backend, max_answer_words=10)

    answer = a.chat("When is the workshop?")

    assert answer == "The workshop is at 14:00."
    shorten_messages = backend.calls[1]
    assert "at most 10 words" in shorten_messages[0]["content"]
    assert "When is the workshop?" in shorten_messages[1]["content"]
    assert LONG_ANSWER in shorten_messages[1]["content"]
    # what was said is what the conversation remembers
    assert a.history[-1] == {"role": "assistant", "content": "The workshop is at 14:00."}


def test_reformulation_still_too_long_is_trimmed_to_whole_sentences(isolated_vector_store):
    backend = _ScriptedBackend(LONG_ANSWER, "The workshop is at 14:00. It is in room B12 on the second floor.")
    a = Assistant(llm=backend, max_answer_words=8)

    assert a.chat("When is the workshop?") == "The workshop is at 14:00."


def test_failed_reformulation_trims_the_original_answer(isolated_vector_store):
    backend = _ScriptedBackend(LONG_ANSWER, RuntimeError("LLM down"))
    a = Assistant(llm=backend, max_answer_words=10)

    assert a.chat("When is the workshop?") == " ".join(["word"] * 10) + "..."


def test_max_answer_words_none_disables_shortening(isolated_vector_store):
    backend = _ScriptedBackend(LONG_ANSWER)
    a = Assistant(llm=backend, max_answer_words=None)

    assert a.chat("When is the workshop?") == LONG_ANSWER


def test_add_documents_makes_them_retrievable(isolated_vector_store, tmp_path, fake_backend):
    doc = tmp_path / "extra.txt"
    doc.write_text("The Smart Mirror SDK ships a gesture-driven UI.", encoding="utf-8")
    backend = fake_backend(reply="It ships a gesture-driven UI.")

    a = Assistant(llm=backend)
    a.add_documents(str(doc))
    a.chat("What does the Smart Mirror SDK ship?")

    user_message = backend.calls[-1]["messages"][-1]["content"]
    assert "gesture-driven UI" in user_message


def test_system_prompt_instructs_against_acting_on_placeholder_meta_commentary(
    isolated_vector_store, tmp_path, fake_backend
):
    """Guards against two failure modes seen live: (1) treating retrieved
    developer notes ("replace this file", "TODO") as real content to act on
    or mention, and (2) inventing a plausible-sounding answer when the
    retrieved context is thin/placeholder instead of admitting uncertainty."""
    doc = tmp_path / "placeholder.txt"
    doc.write_text(
        "This is a placeholder description of IEEE INSAT. TODO: replace this file before shipping.",
        encoding="utf-8",
    )
    backend = fake_backend(reply="I don't have verified information about that yet.")

    a = Assistant(llm=backend)
    a.add_documents(str(doc))
    a.chat("What is IEEE INSAT?")

    sent_messages = backend.calls[-1]["messages"]
    system_message = sent_messages[0]["content"].lower()
    user_message = sent_messages[-1]["content"].lower()

    assert sent_messages[0]["role"] == "system"
    # the placeholder chunk was actually retrieved into the prompt...
    assert "placeholder" in user_message
    assert "replace this file" in user_message
    # ...but the system prompt tells the model not to act on/repeat text
    # like that, and to admit uncertainty instead of inventing an answer
    assert "only using facts stated in the retrieved context" in system_message
    assert "i don't have verified information about that yet" in system_message
    assert "placeholder" in system_message
    assert "todo" in system_message
    assert "replace this file" in system_message


def test_voice_chat_requires_stt(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend())
    with pytest.raises(ValueError):
        a.voice_chat()


def test_voice_chat_answers_the_question_that_followed_the_wake_word(isolated_vector_store, fake_backend, monkeypatch):
    """wake word -> STT -> chat() -- the pipeline voice_chat is required to reuse, not reimplement."""
    backend = fake_backend(reply="IEEE INSAT is the IEEE student branch at INSAT.")
    a = Assistant(llm=backend, stt=True)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "what is IEEE INSAT?")

    answer = a.voice_chat()

    assert answer == "IEEE INSAT is the IEEE student branch at INSAT."
    assert backend.calls[-1]["messages"][-1]["content"] == "what is IEEE INSAT?"


def test_voice_chat_speaks_the_reply_when_tts_enabled(isolated_vector_store, fake_backend, monkeypatch):
    a = Assistant(llm=fake_backend(reply="some answer"), stt=True, tts=True)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "a question")
    spoken = []
    monkeypatch.setattr(a.tts, "speak", lambda text: spoken.append(text))

    a.voice_chat()

    assert spoken == ["some answer"]


def test_stt_and_tts_are_constructed_when_enabled(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True, tts=True)

    assert a.stt is not None
    assert a.wake_word_detector is not None
    assert a.hal is not None
    assert a.tts.enabled is True


class _StopLoop(Exception):
    """Sentinel to break out of listen_loop's `while True` from inside a test."""


@pytest.mark.asyncio
async def test_listen_loop_survives_a_bad_turn_and_keeps_listening(
    isolated_vector_store, fake_backend, monkeypatch, caplog
):
    """One turn raising (LLM hiccup, transient STT error, ...) must not kill the loop."""
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True)

    attempts = iter(["boom", "a real question"])

    def flaky_listen_for_wake_word(audio_blocks):
        question = next(attempts)
        if question == "boom":
            raise RuntimeError("boom")
        return question

    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", flaky_listen_for_wake_word)

    results = []

    def on_result(payload):
        results.append(payload)
        raise _StopLoop

    with caplog.at_level("ERROR", logger="smartmirror.assistant.assistant"):
        with pytest.raises(_StopLoop):
            await a.listen_loop(on_result=on_result)

    # the failed turn was logged, not silently swallowed or fatal
    assert any("Voice turn failed" in message for message in caplog.messages)
    # and the loop moved on to the next turn instead of dying
    assert results == [{"transcript": "a real question", "answer": "the answer"}]


@pytest.mark.asyncio
async def test_listen_loop_runs_turns_and_reports_each_via_on_result(isolated_vector_store, fake_backend, monkeypatch):
    """wake_window_seconds=None: each turn is independently wake-word-gated,
    which is what this test is about -- the wake window itself is covered
    separately below."""
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=None)
    questions = iter(["what is IEEE INSAT?", "what time is it?"])
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: next(questions))

    results = []

    def on_result(payload):
        results.append(payload)
        if len(results) >= 2:
            raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(on_result=on_result)

    assert results == [
        {"transcript": "what is IEEE INSAT?", "answer": "the answer"},
        {"transcript": "what time is it?", "answer": "the answer"},
    ]


@pytest.mark.asyncio
async def test_listen_loop_supports_an_async_on_result_callback(isolated_vector_store, fake_backend, monkeypatch):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "a question")

    results = []

    async def on_result(payload):
        results.append(payload)
        raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(on_result=on_result)

    assert results == [{"transcript": "a question", "answer": "the answer"}]


@pytest.mark.asyncio
async def test_listen_loop_requires_stt(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend())
    with pytest.raises(ValueError):
        await a.listen_loop()


@pytest.mark.asyncio
async def test_listen_loop_uses_the_hal_passed_in_over_the_default(isolated_vector_store, fake_backend, monkeypatch):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "a question")

    other_hal = MagicMock()
    other_hal.read_audio.return_value = iter([])

    def on_result(payload):
        raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(hal=other_hal, on_result=on_result)

    assert a.hal is other_hal



@pytest.mark.asyncio
async def test_listen_loop_reports_the_question_then_the_answer_before_speaking_it(
    isolated_vector_store, fake_backend, monkeypatch
):
    """on_question fires before the LLM call and on_answer before TTS, so a UI
    can react while the answer is still being generated/spoken."""
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=None)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "a question")

    calls = []
    real_chat = a.chat
    monkeypatch.setattr(a, "chat", lambda message: calls.append("chat") or real_chat(message))
    monkeypatch.setattr(a.tts, "speak", lambda text: calls.append(("speak", text)))

    async def on_question(question):
        calls.append(("question", question))

    def on_result(payload):
        calls.append("result")
        raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(
            on_question=on_question,
            on_answer=lambda answer: calls.append(("answer", answer)),
            on_result=on_result,
        )

    assert calls == [("question", "a question"), "chat", ("answer", "the answer"), ("speak", "the answer"), "result"]


@pytest.mark.asyncio
async def test_listen_loop_wake_word_alone_wakes_without_answering_and_opens_the_window(
    isolated_vector_store, fake_backend, monkeypatch
):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=60)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "")
    monkeypatch.setattr(a.stt, "listen", lambda hal, deadline=None: "the follow-up")

    questions = []
    results = []

    def on_result(payload):
        results.append(payload)
        raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(on_question=questions.append, on_result=on_result)

    # "" = wake word heard alone (no LLM call); the follow-up needed no wake word
    assert questions == ["", "the follow-up"]
    assert results == [{"transcript": "the follow-up", "answer": "the answer"}]


@pytest.mark.asyncio
async def test_listen_loop_returns_once_stop_event_is_set(isolated_vector_store, fake_backend, monkeypatch):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=None)
    stop_event = threading.Event()

    def heard_while_shutting_down(audio_blocks):
        stop_event.set()
        return ""  # what listen_for_wake_word returns once HAL.close() ends the stream

    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", heard_while_shutting_down)
    questions = []

    await asyncio.wait_for(a.listen_loop(on_question=questions.append, stop_event=stop_event), timeout=5)

    assert questions == []  # a turn interrupted by shutdown isn't reported

def test_default_wake_window_is_180_seconds(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True)
    assert a.wake_window_seconds == 180


def test_wake_window_seconds_zero_disables_the_window(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True, wake_window_seconds=0)
    assert a.wake_window_seconds is None


@pytest.mark.asyncio
async def test_wake_window_opens_after_a_match_and_skips_the_wake_word_on_the_next_turn(
    isolated_vector_store, fake_backend, monkeypatch, caplog
):
    """After a successful turn, the *next* turn must go through stt.listen()
    (no wake word needed) instead of wake_word_detector.listen_for_wake_word
    again.

    _StopLoop is raised from on_result, not from inside a mocked
    wake_word_detector/stt call -- listen_loop's per-turn try/except (see
    test_listen_loop_survives_a_bad_turn_and_keeps_listening) would catch,
    log, and swallow an exception raised from inside _voice_turn instead of
    letting it end the test.
    """
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=60)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "first question")

    continued_calls = []

    def fake_stt_listen(hal, deadline=None):
        continued_calls.append(deadline)
        return "second question"

    monkeypatch.setattr(a.stt, "listen", fake_stt_listen)

    turns = []

    def on_result(payload):
        turns.append(payload)
        if len(turns) >= 2:
            raise _StopLoop

    with caplog.at_level("INFO", logger="smartmirror.assistant.assistant"):
        with pytest.raises(_StopLoop):
            await a.listen_loop(on_result=on_result)

    assert len(continued_calls) == 1
    assert continued_calls[0] is not None  # a real deadline was passed through
    assert turns[1] == {"transcript": "second question", "answer": "the answer"}
    assert any("Wake window open until" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_wake_window_closes_after_inactivity_and_requires_wake_word_again(
    isolated_vector_store, fake_backend, monkeypatch, caplog
):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=0.05)

    wake_word_calls = []

    def fake_wake_word(audio_blocks):
        wake_word_calls.append(1)
        return "first question" if len(wake_word_calls) == 1 else "second wake-word question"

    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", fake_wake_word)

    def fake_stt_listen(hal, deadline=None):
        # simulate genuine inactivity: nothing heard before the deadline
        time.sleep(max(0.0, deadline - time.monotonic()))
        return ""

    monkeypatch.setattr(a.stt, "listen", fake_stt_listen)

    def on_result(payload):
        if len(wake_word_calls) >= 2:
            raise _StopLoop

    with caplog.at_level("INFO", logger="smartmirror.assistant.assistant"):
        with pytest.raises(_StopLoop):
            await a.listen_loop(on_result=on_result)

    # required again after the window closed from inactivity
    assert len(wake_word_calls) == 2
    assert any("Wake window closed, listening for" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_wake_window_deadline_resets_on_each_continued_turn(isolated_vector_store, fake_backend, monkeypatch):
    """"reset on activity" per the design: every turn inside the window pushes
    the deadline further out, rather than closing at a fixed time from when
    the window first opened."""
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=60)
    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", lambda audio_blocks: "first question")

    deadlines_seen = []
    responses = iter(["second question", "third question"])

    def fake_stt_listen(hal, deadline=None):
        deadlines_seen.append(deadline)
        return next(responses)

    monkeypatch.setattr(a.stt, "listen", fake_stt_listen)

    turns = []

    def on_result(payload):
        turns.append(payload)
        if len(turns) >= 3:
            raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(on_result=on_result)

    assert len(deadlines_seen) == 2
    assert deadlines_seen[1] > deadlines_seen[0]


@pytest.mark.asyncio
async def test_wake_window_disabled_always_requires_the_wake_word(isolated_vector_store, fake_backend, monkeypatch):
    a = Assistant(llm=fake_backend(reply="the answer"), stt=True, wake_window_seconds=None)

    wake_word_calls = []

    def fake_wake_word(audio_blocks):
        wake_word_calls.append(1)
        return "a question"

    monkeypatch.setattr(a.wake_word_detector, "listen_for_wake_word", fake_wake_word)

    def on_result(payload):
        if len(wake_word_calls) >= 2:
            raise _StopLoop

    with pytest.raises(_StopLoop):
        await a.listen_loop(on_result=on_result)

    assert len(wake_word_calls) == 2  # never skipped, no window ever opens


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


def test_voice_listeners_share_one_noise_floor(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True)

    noise_floor = a.stt.vad_kwargs["noise_floor"]
    assert a.wake_word_detector.vad_kwargs["noise_floor"] is noise_floor
    assert noise_floor.ratio == 2.0


def test_noise_ratio_none_keeps_the_fixed_threshold(isolated_vector_store, fake_backend):
    a = Assistant(llm=fake_backend(), stt=True, noise_ratio=None)

    assert a.stt.vad_kwargs == {}
    assert a.wake_word_detector.vad_kwargs == {}
