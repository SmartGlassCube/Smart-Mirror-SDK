import numpy as np

from smartmirror.assistant.stt.vad import capture_utterance

LOUD = np.full(10, 5000, dtype=np.int16)
QUIET = np.zeros(10, dtype=np.int16)


def test_captures_speech_bounded_by_silence():
    blocks = [QUIET, QUIET, LOUD, LOUD, LOUD] + [QUIET] * 15

    utterance = capture_utterance(iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=2)

    assert utterance is not None
    assert len(utterance) == 3 * 10 + 15 * 10  # speech + the trailing silence run that ended it


def test_discards_utterance_shorter_than_min_speech_blocks():
    blocks = [LOUD] + [QUIET] * 15 + [LOUD, LOUD, LOUD] + [QUIET] * 15

    utterance = capture_utterance(iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=2)

    # first (too-short) utterance discarded, second one returned
    assert utterance is not None
    assert len(utterance) == 3 * 10 + 15 * 10


def test_returns_none_when_stream_ends_without_a_full_utterance():
    blocks = [QUIET, QUIET, QUIET]

    assert capture_utterance(iter(blocks), threshold=500) is None


def test_leading_silence_before_speech_is_discarded():
    blocks = [QUIET] * 5 + [LOUD, LOUD] + [QUIET] * 15

    utterance = capture_utterance(iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=2)

    assert utterance is not None
    assert len(utterance) == 2 * 10 + 15 * 10


def test_hits_max_total_blocks_cap():
    blocks = [LOUD] * 50

    utterance = capture_utterance(
        iter(blocks), threshold=500, silence_blocks=100, min_speech_blocks=2, max_total_blocks=10
    )

    assert utterance is not None
    assert len(utterance) == 10 * 10


def test_logs_when_an_utterance_is_captured(caplog):
    blocks = [LOUD, LOUD] + [QUIET] * 15

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.vad"):
        capture_utterance(iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=2)

    assert any("utterance captured" in message for message in caplog.messages)


def test_does_not_log_a_capture_when_stream_ends_without_one(caplog):
    blocks = [QUIET, QUIET]

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.vad"):
        capture_utterance(iter(blocks), threshold=500)

    assert not any("utterance captured" in message for message in caplog.messages)
