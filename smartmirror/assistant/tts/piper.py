"""Piper TTS wrapper for local, offline text-to-speech synthesis."""


class PiperTTS:
    """Synthesises speech from text using a local Piper TTS model."""

    def __init__(self, model_path: str, language: str = "en") -> None:
        pass

    def speak(self, text: str) -> None:
        """Synthesise *text* and play the resulting audio through the default output."""
        pass

    def synthesise(self, text: str, output_path: str) -> None:
        """Synthesise *text* and save the audio to *output_path*."""
        pass
