"""Speech-to-text via pywhispercpp.

STUB for phase 1 -- no audio capture or transcription is implemented yet.
Phase 2 wires this to an actual microphone and pywhispercpp model.
"""


class WhisperSTT:
    """Wraps pywhispercpp for offline speech-to-text. Not implemented yet."""

    def __init__(self, model: str = "base.en", language: str = "en"):
        self.model = model
        self.language = language

    def transcribe(self, audio=None) -> str:
        """Transcribe audio to text.

        Args:
            audio: audio samples/path (shape TBD in phase 2).
        """
        raise NotImplementedError("WhisperSTT.transcribe is implemented in phase 2")

    def listen(self) -> str:
        """Capture audio from the microphone and transcribe it."""
        raise NotImplementedError("WhisperSTT.listen is implemented in phase 2")
