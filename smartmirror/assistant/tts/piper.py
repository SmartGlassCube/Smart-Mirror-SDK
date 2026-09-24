"""Text-to-speech via Piper.

STUB for phase 1 -- no audio synthesis or playback is implemented yet.
Phase 2 wires this to the actual Piper binary/voices.

Gated behind an `enabled` flag: when disabled, speak() is a silent no-op
rather than raising, so callers don't need to branch on whether TTS is on.
"""


class PiperTTS:
    """Wraps the Piper TTS engine. Synthesis is not implemented yet."""

    def __init__(self, enabled: bool = False, voice: str = "en_US-lessac-medium"):
        self.enabled = enabled
        self.voice = voice

    def speak(self, text: str) -> None:
        """Synthesize and play `text`. No-op when disabled."""
        if not self.enabled:
            return
        raise NotImplementedError("PiperTTS.speak is implemented in phase 2")
