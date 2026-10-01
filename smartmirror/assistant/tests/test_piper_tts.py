from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from smartmirror.assistant.tts import PiperTTS

LOAD_PATH = "piper.PiperVoice.load"


def _fake_voice(samplerate=22050, samples=None):
    if samples is None:
        samples = np.array([100, -100, 200, -200], dtype=np.int16)

    def fake_synthesize_wav(text, wav_file, *args, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(samples.tobytes())

    voice = MagicMock()
    voice.synthesize_wav.side_effect = fake_synthesize_wav
    return voice, samples, samplerate


def _touch_voice_files(voices_dir, voice_name="en_US-lessac-medium"):
    onnx_path = voices_dir / f"{voice_name}.onnx"
    config_path = voices_dir / f"{voice_name}.onnx.json"
    onnx_path.write_bytes(b"")
    config_path.write_text("{}", encoding="utf-8")


def test_speak_is_a_no_op_when_disabled():
    tts = PiperTTS(enabled=False)
    tts.speak("hello")  # must not raise, must not touch piper at all


def test_speak_synthesizes_and_plays_through_hal(tmp_path):
    _touch_voice_files(tmp_path)
    voice, samples, samplerate = _fake_voice()
    hal = MagicMock()

    with patch(LOAD_PATH, return_value=voice):
        tts = PiperTTS(enabled=True, voices_dir=str(tmp_path), hal=hal)
        tts.speak("hello world")

    voice.synthesize_wav.assert_called_once()
    assert voice.synthesize_wav.call_args.args[0] == "hello world"

    hal.play_audio.assert_called_once()
    played_samples, played_kwargs = hal.play_audio.call_args.args[0], hal.play_audio.call_args.kwargs
    assert np.array_equal(played_samples, samples)
    assert played_kwargs["samplerate"] == samplerate


def test_voice_loaded_once_and_reused_across_calls(tmp_path):
    _touch_voice_files(tmp_path)
    voice, *_ = _fake_voice()
    hal = MagicMock()

    with patch(LOAD_PATH, return_value=voice) as mock_load:
        tts = PiperTTS(enabled=True, voices_dir=str(tmp_path), hal=hal)
        tts.speak("one")
        tts.speak("two")

    mock_load.assert_called_once()
    assert voice.synthesize_wav.call_count == 2


def test_speak_without_hal_does_not_raise(tmp_path):
    _touch_voice_files(tmp_path)
    voice, *_ = _fake_voice()

    with patch(LOAD_PATH, return_value=voice):
        tts = PiperTTS(enabled=True, voices_dir=str(tmp_path), hal=None)
        tts.speak("hello")  # must not raise even with no HAL to play through


def test_missing_voice_files_raises_clear_error(tmp_path):
    tts = PiperTTS(enabled=True, voices_dir=str(tmp_path))

    with pytest.raises(RuntimeError, match="download_voices"):
        tts.speak("hello")
