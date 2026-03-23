"""pywhispercpp wrapper for local, offline speech-to-text transcription."""


class WhisperSTT:
    """Transcribes audio to text using a local Whisper model via pywhispercpp."""

    def __init__(self, model: str = "base", language: str = "en") -> None:
        pass

    def transcribe(self, audio_path: str) -> str:
        """Transcribe the audio file at *audio_path* and return the transcript."""
        pass

    def listen(self) -> str:
        """Capture microphone input and return the transcribed text."""
        pass
