import asyncio
import threading
from types import SimpleNamespace

from smartmirror.assistant.assistant import FAILURE_BACKOFF_MAX_SECONDS, Assistant


class RecordingStop(threading.Event):
    """A stop event that records each backoff wait instead of sleeping, and stops the loop after `limit` of them."""

    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.waits = []

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if len(self.waits) >= self.limit:
            self.set()
        return self.is_set()


def bare_assistant(hear):
    """An Assistant with only what listen_loop touches -- no Whisper/LLM/embedder loading."""
    assistant = Assistant.__new__(Assistant)
    assistant.stt = object()
    assistant.hal = None
    assistant.wake_window_seconds = None
    assistant.wake_word_detector = SimpleNamespace(wake_word="ABDOU")
    assistant._hear_question = hear
    return assistant


def test_repeated_failures_back_off_exponentially_up_to_the_cap():
    def no_microphone(*_args):
        raise RuntimeError("Error querying device -1")

    stop = RecordingStop(limit=7)
    asyncio.run(bare_assistant(no_microphone).listen_loop(stop_event=stop))

    assert stop.waits == [1, 2, 4, 8, 16, FAILURE_BACKOFF_MAX_SECONDS, FAILURE_BACKOFF_MAX_SECONDS]


def test_a_successful_turn_resets_the_backoff():
    outcomes = iter(["fail", "fail", "ok", "fail"])

    def hear(*_args):
        # "ok" is a quiet turn: no exception, nothing heard (returns None).
        if next(outcomes) == "fail":
            raise RuntimeError("mic stream dropped")

    stop = RecordingStop(limit=3)
    asyncio.run(bare_assistant(hear).listen_loop(stop_event=stop))

    assert stop.waits == [1, 2, 1]
