"""Text-to-speech via Piper, gated behind an explicit `enabled` flag.

piper is imported lazily inside _ensure_voice() so importing this module
doesn't require it to be installed, and speak() is a silent no-op when
disabled so callers never need to branch on whether TTS is on.

Unlike pywhispercpp's STT models, Piper voices are not auto-downloaded here
-- speak() raises a clear error with the download command instead of making
a surprise network call the first time someone talks to the assistant.
"""

import io
import os
import wave

import numpy as np

DEFAULT_VOICE = "en_US-lessac-medium"
DEFAULT_VOICES_DIR = os.path.expanduser("~/.local/share/smartmirror/piper_voices")


class PiperTTS:
    """Wraps a Piper voice model for offline text-to-speech."""

    def __init__(self, enabled: bool = False, voice: str = DEFAULT_VOICE, voices_dir: str = None, hal=None):
        self.enabled = enabled
        self.voice_name = voice
        self.voices_dir = voices_dir or DEFAULT_VOICES_DIR
        self.hal = hal
        self._voice = None

    def _ensure_voice(self):
        if self._voice is None:
            from piper import PiperVoice

            onnx_path = os.path.join(self.voices_dir, f"{self.voice_name}.onnx")
            config_path = f"{onnx_path}.json"
            if not os.path.exists(onnx_path) or not os.path.exists(config_path):
                raise RuntimeError(
                    f"Piper voice '{self.voice_name}' not found in {self.voices_dir}. Download it first: "
                    f"python -m piper.download_voices {self.voice_name} --download-dir {self.voices_dir}"
                )
            self._voice = PiperVoice.load(onnx_path, config_path)
        return self._voice

    def speak(self, text: str) -> None:
        """Synthesize `text` and play it through HAL. No-op when disabled."""
        if not self.enabled:
            return

        voice = self._ensure_voice()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        buffer.seek(0)

        with wave.open(buffer, "rb") as wav_file:
            samplerate = wav_file.getframerate()
            raw = wav_file.readframes(wav_file.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16)

        if self.hal is not None:
            self.hal.play_audio(samples, samplerate=samplerate)
