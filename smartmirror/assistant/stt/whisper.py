"""Speech-to-text via pywhispercpp (whisper.cpp bindings) -- fully offline.

pywhispercpp is imported lazily inside _ensure_model() so importing this
module doesn't require it to be installed, and named models (e.g. "base.en")
are downloaded by pywhispercpp itself on first use.
"""

import logging
import re

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "base.en"
WHISPER_SAMPLE_RATE = 16000

# Whisper's non-speech annotations: "[BLANK_AUDIO]", "[ Background noise ]",
# "[INTERPOSING VOICES]", "(music)", "*laughs*", ... Seen constantly in a noisy
# room; left in, they'd reach the LLM as a "question" during the wake window.
NON_SPEECH_PATTERN = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")

# whisper.cpp defaults to min(4, cpu_count()) inference threads of its own,
# on top of mediapipe's XNNPACK thread pool (camera_loop) and PortAudio's
# I/O thread (HAL) already running concurrently. On a 4-core Pi that's real
# contention, not just extra CPU load -- capping it here leaves headroom for
# the rest of the pipeline. Pass n_threads=None to defer to pywhispercpp's
# own default instead (e.g. on beefier hardware).
DEFAULT_N_THREADS = 2


class WhisperSTT:
    """Wraps a whisper.cpp model for offline speech-to-text."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        language: str = "en",
        models_dir: str = None,
        n_threads: int = DEFAULT_N_THREADS,
        vad_kwargs: dict = None,
    ):
        self.model_name = model
        self.vad_kwargs = vad_kwargs or {}
        self.language = language
        self.models_dir = models_dir
        self.n_threads = n_threads
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from pywhispercpp.model import Model

            kwargs = {}
            if self.models_dir:
                kwargs["models_dir"] = self.models_dir
            # .en models are English-only and reject an explicit language param.
            if self.language and not self.model_name.endswith(".en"):
                kwargs["language"] = self.language
            if self.n_threads is not None:
                kwargs["n_threads"] = self.n_threads

            logger.info("Loading whisper.cpp model %r (n_threads=%s)...", self.model_name, self.n_threads)
            self._model = Model(self.model_name, **kwargs)
        return self._model

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe mono audio sampled at 16kHz (int16 or float32) to text.

        Non-speech annotations (see NON_SPEECH_PATTERN) are dropped, so noise
        alone transcribes to "".
        """
        model = self._ensure_model()
        segments = model.transcribe(self._normalize(audio))
        text = " ".join(segment.text.strip() for segment in segments).strip()
        logger.info("Whisper transcript: %r", text)
        return " ".join(NON_SPEECH_PATTERN.sub(" ", text).split())

    def listen(self, hal, deadline: float = None) -> str:
        """Capture one VAD-gated utterance from `hal` and transcribe it.

        `deadline`, if given, is a `time.monotonic()` timestamp: stop
        waiting for speech to start (and return "") once passed -- see
        vad.capture_utterance.
        """
        from .vad import capture_utterance

        audio = capture_utterance(hal.read_audio(), deadline=deadline, **self.vad_kwargs)
        if audio is None:
            return ""
        return self.transcribe(audio)

    @staticmethod
    def _normalize(audio: np.ndarray) -> np.ndarray:
        if audio.dtype == np.int16:
            return audio.astype(np.float32) / 32768.0
        return audio.astype(np.float32)
