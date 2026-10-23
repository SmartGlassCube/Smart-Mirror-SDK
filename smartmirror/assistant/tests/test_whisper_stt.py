from unittest.mock import MagicMock, patch

import numpy as np

from smartmirror.assistant.stt import WhisperSTT

MODEL_PATH = "pywhispercpp.model.Model"

LOUD = np.full(10, 5000, dtype=np.int16)
QUIET = np.zeros(10, dtype=np.int16)


def _fake_model(text: str):
    segment = MagicMock()
    segment.text = text
    model = MagicMock()
    model.transcribe.return_value = [segment]
    return model


class FakeHAL:
    def __init__(self, blocks):
        self._blocks = blocks

    def read_audio(self):
        return iter(self._blocks)


def test_transcribe_joins_segment_text():
    fake_model = _fake_model("hello world")

    with patch(MODEL_PATH, return_value=fake_model) as mock_model_cls:
        stt = WhisperSTT(model="base.en")
        result = stt.transcribe(np.zeros(1600, dtype=np.int16))

    assert result == "hello world"
    mock_model_cls.assert_called_once_with("base.en", n_threads=2)


def test_transcribe_converts_int16_to_normalized_float32():
    fake_model = _fake_model("ok")

    with patch(MODEL_PATH, return_value=fake_model):
        stt = WhisperSTT(model="base.en")
        stt.transcribe(np.array([16384, -16384], dtype=np.int16))

    (passed_audio,), _kwargs = fake_model.transcribe.call_args
    assert passed_audio.dtype == np.float32
    assert np.allclose(passed_audio, [0.5, -0.5], atol=1e-3)


def test_model_loaded_once_and_reused_across_calls():
    fake_model = _fake_model("ok")

    with patch(MODEL_PATH, return_value=fake_model) as mock_model_cls:
        stt = WhisperSTT(model="base.en")
        stt.transcribe(np.zeros(10, dtype=np.int16))
        stt.transcribe(np.zeros(10, dtype=np.int16))

    mock_model_cls.assert_called_once()


def test_non_english_only_model_passes_language_kwarg():
    fake_model = _fake_model("bonjour")

    with patch(MODEL_PATH, return_value=fake_model) as mock_model_cls:
        stt = WhisperSTT(model="base", language="fr")
        stt.transcribe(np.zeros(10, dtype=np.int16))

    mock_model_cls.assert_called_once_with("base", language="fr", n_threads=2)


def test_english_only_model_does_not_pass_language_kwarg():
    fake_model = _fake_model("hi")

    with patch(MODEL_PATH, return_value=fake_model) as mock_model_cls:
        stt = WhisperSTT(model="base.en", language="en")
        stt.transcribe(np.zeros(10, dtype=np.int16))

    mock_model_cls.assert_called_once_with("base.en", n_threads=2)


def test_transcribe_always_logs_the_raw_transcript(caplog):
    """Not just on a wake-word match -- a failed match needs to be visible too."""
    fake_model = _fake_model("turn on the lights")

    with patch(MODEL_PATH, return_value=fake_model), caplog.at_level(
        "INFO", logger="smartmirror.assistant.stt.whisper"
    ):
        stt = WhisperSTT(model="base.en")
        stt.transcribe(np.zeros(10, dtype=np.int16))

    assert any("turn on the lights" in message for message in caplog.messages)


def test_transcribe_drops_whispers_non_speech_annotations():
    fake_model = _fake_model("[INTERPOSING VOICES] what is (coughs) IEEE INSAT *laughs*")

    with patch(MODEL_PATH, return_value=fake_model):
        stt = WhisperSTT(model="base.en")
        result = stt.transcribe(np.zeros(10, dtype=np.int16))

    assert result == "what is IEEE INSAT"


def test_transcribe_of_noise_alone_is_empty():
    """So the wake window doesn't send "[ Background noise ]" to the LLM as a question."""
    fake_model = _fake_model("[ Background noise ]")

    with patch(MODEL_PATH, return_value=fake_model):
        stt = WhisperSTT(model="base.en")
        result = stt.transcribe(np.zeros(10, dtype=np.int16))

    assert result == ""


def test_n_threads_none_defers_to_pywhispercpps_own_default():
    fake_model = _fake_model("ok")

    with patch(MODEL_PATH, return_value=fake_model) as mock_model_cls:
        stt = WhisperSTT(model="base.en", n_threads=None)
        stt.transcribe(np.zeros(10, dtype=np.int16))

    mock_model_cls.assert_called_once_with("base.en")


def test_listen_captures_one_vad_gated_utterance_and_transcribes_it():
    """listen() uses vad.capture_utterance's defaults: 3+ loud blocks, then 15 quiet to end it."""
    fake_model = _fake_model("what is IEEE INSAT")
    hal = FakeHAL([LOUD, LOUD, LOUD] + [QUIET] * 15)

    with patch(MODEL_PATH, return_value=fake_model):
        stt = WhisperSTT(model="base.en")
        result = stt.listen(hal)

    assert result == "what is IEEE INSAT"


def test_listen_returns_empty_string_if_no_utterance_captured():
    hal = FakeHAL([QUIET, QUIET])
    stt = WhisperSTT(model="base.en")

    assert stt.listen(hal) == ""
