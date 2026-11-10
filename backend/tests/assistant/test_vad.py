import numpy as np

from smartmirror.assistant.stt.vad import NoiseFloor, capture_utterance

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


CHATTER = np.full(10, 1500, dtype=np.int16)  # background voices: over the fixed 500 threshold
NEAR_VOICE = np.full(10, 6000, dtype=np.int16)  # someone at the mirror


def test_noise_floor_ignores_steady_background_chatter():
    noise_floor = NoiseFloor(ratio=2.0)
    blocks = [CHATTER] * 200

    assert capture_utterance(iter(blocks), threshold=500, min_speech_blocks=3, noise_floor=noise_floor) is None
    assert noise_floor.level == 1500


def test_noise_floor_still_hears_a_near_voice_over_the_chatter():
    noise_floor = NoiseFloor(ratio=2.0)
    blocks = [CHATTER] * 50 + [NEAR_VOICE] * 5 + [CHATTER] * 15

    utterance = capture_utterance(
        iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=3, noise_floor=noise_floor
    )

    assert utterance is not None
    assert len(utterance) == 5 * 10 + 15 * 10  # chatter around the voice counts as silence


def test_noise_floor_persists_across_utterances():
    """One NoiseFloor is shared by the wake-word and follow-up listeners: what it learnt carries over."""
    noise_floor = NoiseFloor(ratio=2.0)
    capture_utterance(iter([CHATTER] * 50), threshold=500, noise_floor=noise_floor)

    assert capture_utterance(iter([CHATTER] * 20), threshold=500, min_speech_blocks=3, noise_floor=noise_floor) is None


def test_noise_floor_in_a_quiet_room_keeps_the_fixed_threshold():
    noise_floor = NoiseFloor(ratio=2.0)
    blocks = [QUIET] * 50 + [LOUD, LOUD, LOUD] + [QUIET] * 15

    utterance = capture_utterance(
        iter(blocks), threshold=500, silence_blocks=15, min_speech_blocks=2, noise_floor=noise_floor
    )

    assert utterance is not None
    assert noise_floor.threshold(500) == 500


def test_noise_floor_needs_a_warmup_before_estimating():
    noise_floor = NoiseFloor(ratio=2.0)
    for _ in range(5):
        noise_floor.observe(1500)

    assert noise_floor.level == 0.0


def test_noise_floor_hears_nothing_until_it_has_heard_the_room():
    noise_floor = NoiseFloor(ratio=2.0)

    assert noise_floor.threshold(500) == float("inf")
