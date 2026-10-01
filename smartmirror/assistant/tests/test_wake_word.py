import numpy as np
import pytest

from smartmirror.assistant.stt.wake_word import WAKE_WORD_VARIANTS, WakeWordDetector

# The 8 real mishearings confirmed from base.en transcription logs (the b/d
# plosives in "abdou" get dropped/softened, leaving the vowel skeleton).
CONFIRMED_MISHEARINGS = [
    "up to",
    "add two",
    "up through",
    "up there",
    "updo",
    "ado",
    "appdo",
    "and do",
]

LOUD = np.full(10, 5000, dtype=np.int16)
QUIET = np.zeros(10, dtype=np.int16)
VAD_KWARGS = {"threshold": 500, "silence_blocks": 3, "min_speech_blocks": 1}


class FakeSTT:
    """Returns canned transcripts in order, one per captured utterance."""

    def __init__(self, transcripts):
        self._transcripts = list(transcripts)
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return self._transcripts.pop(0)


def _utterance_blocks(n=1):
    return [LOUD] + [QUIET] * 3


def test_matches_exact_wake_word_and_returns_remainder():
    stt = FakeSTT(["ABDOU what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what is IEEE INSAT"


def test_fuzzy_matches_asr_mishearing_of_the_wake_word():
    """tiny.en actually transcribes "ABDOU" as "Abdu" in practice -- must still match."""
    stt = FakeSTT(["Abdu, what is IEEE INSAT?"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what is IEEE INSAT?"


def test_discards_non_matching_utterances_and_keeps_listening():
    stt = FakeSTT(["turn on the lights", "ABDOU what time is it"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)
    blocks = _utterance_blocks() + _utterance_blocks()

    result = detector.listen_for_wake_word(iter(blocks))

    assert result == "what time is it"
    assert stt.calls == 2


def test_wake_word_alone_returns_empty_remainder():
    stt = FakeSTT(["ABDOU"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == ""


def test_returns_empty_string_when_stream_ends_unmatched():
    stt = FakeSTT([])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter([QUIET, QUIET]))

    assert result == ""
    assert stt.calls == 0


def test_matches_wake_word_split_across_two_tokens_mid_transcript():
    """"and do" is a confirmed real mishearing (now an exact WAKE_WORD_VARIANTS
    hit, see the parametrized test below) that also happens to clear the
    fuzzy threshold on its own -- this specifically checks position
    independence, which both layers need regardless of which one matches."""
    stt = FakeSTT(["hey and do what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what is IEEE INSAT"


def test_matches_wake_word_as_a_single_word_not_in_first_position():
    stt = FakeSTT(["hey abdu what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what is IEEE INSAT"


def test_does_not_match_short_fragments_that_score_below_common_words():
    """"Do" alone scores ~0.57 against "abdou" -- lower than "about" (0.80)
    or "radio"/"above" (0.60), which must NOT wake the assistant. Lowering
    the threshold to catch it would also catch those words, so this is an
    intentional non-match, not a regression (see
    test_known_false_positive_risk below for the tradeoff this is guarding
    against). Unlike "add two"/"and do" (see the confirmed-mishearing tests
    below), "Do" alone was never reported as a real mishearing, so it isn't
    in WAKE_WORD_VARIANTS either -- it has to clear fuzzy matching on its
    own, and doesn't."""
    stt = FakeSTT(["Do what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    # should not match -- exhausts the fake STT's canned transcript and
    # falls through to "stream ended" rather than matching
    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == ""
    assert stt.calls == 1


def test_known_false_positive_risk_documented_not_silently_regressed():
    """"about" scores 0.80 against "abdou" -- character-ratio matching can't
    separate it from the wake word at any threshold that also accepts real
    ASR variants like "anddo" (0.60). This is why the threshold wasn't
    lowered further to chase short fragments (see the test above): doing
    so wouldn't just risk more false positives, it wouldn't even fix the
    "about" collision, which already exists at the current threshold. A
    phonetic matcher would separate these properly -- out of scope here."""
    stt = FakeSTT(["I read about IEEE INSAT yesterday"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "IEEE INSAT yesterday"


@pytest.mark.parametrize("mishearing", CONFIRMED_MISHEARINGS)
def test_matches_each_confirmed_mishearing_standalone(mishearing):
    stt = FakeSTT([f"{mishearing} what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what is IEEE INSAT"


@pytest.mark.parametrize("mishearing", CONFIRMED_MISHEARINGS)
def test_matches_each_confirmed_mishearing_mid_transcript(mishearing):
    """Same as above but with a leading filler word, proving the match isn't
    position-dependent (mirrors the layer-2 fix from the previous round)."""
    stt = FakeSTT([f"hey {mishearing} what time is it"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what time is it"


def test_all_confirmed_mishearings_are_registered_as_variants():
    """Guards against someone trimming WAKE_WORD_VARIANTS without noticing
    it's the fix for these specific, real, previously-failing cases."""
    for mishearing in CONFIRMED_MISHEARINGS:
        assert mishearing in WAKE_WORD_VARIANTS


def test_exact_variant_match_is_tried_before_fuzzy_and_logged_as_such(caplog):
    stt = FakeSTT(["up there what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.wake_word"):
        detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert any("[exact-variant]" in message and "MATCH" in message for message in caplog.messages)
    assert not any("[fuzzy]" in message for message in caplog.messages)


def test_fuzzy_fallback_is_tagged_in_the_log_when_no_variant_matches(caplog):
    stt = FakeSTT(["Abdu, what is IEEE INSAT?"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.wake_word"):
        detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert any("[fuzzy]" in message and "MATCH" in message for message in caplog.messages)


def test_custom_wake_word_does_not_inherit_abdou_specific_variants():
    """WAKE_WORD_VARIANTS is "abdou"-specific -- a different configured wake
    word must not accidentally match on them."""
    stt = FakeSTT(["up there, what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, wake_word="computer", vad_kwargs=VAD_KWARGS)

    assert detector.variants == set()

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == ""


def test_variants_can_be_overridden_explicitly():
    stt = FakeSTT(["hello world what time is it"])
    detector = WakeWordDetector(stt=stt, variants={"hello world"}, vad_kwargs=VAD_KWARGS)

    result = detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert result == "what time is it"


def test_logs_a_successful_match_with_the_heard_text(caplog):
    stt = FakeSTT(["ABDOU what is IEEE INSAT"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.wake_word"):
        detector.listen_for_wake_word(iter(_utterance_blocks()))

    assert any(
        "ABDOU what is IEEE INSAT" in message and "MATCH" in message for message in caplog.messages
    )


def test_logs_a_failed_match_with_the_heard_text_and_reason(caplog):
    stt = FakeSTT(["turn on the lights", "ABDOU what time is it"])
    detector = WakeWordDetector(stt=stt, vad_kwargs=VAD_KWARGS)
    blocks = _utterance_blocks() + _utterance_blocks()

    with caplog.at_level("INFO", logger="smartmirror.assistant.stt.wake_word"):
        detector.listen_for_wake_word(iter(blocks))

    failed_match_logs = [m for m in caplog.messages if "turn on the lights" in m]
    assert failed_match_logs
    assert "no match" in failed_match_logs[0]
