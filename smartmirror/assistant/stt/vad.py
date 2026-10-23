"""Minimal energy-based voice activity detection for utterance segmentation.

No ML and no extra dependencies -- just an RMS threshold over int16 audio
blocks. This is what keeps STT off the hot path while the room is silent;
it is not a substitute for a real VAD model if accuracy ever matters more
than "good enough to gate an expensive call".

Optionally (see NoiseFloor) the threshold follows the room's background
level, so in a room full of chatter only speech clearly louder than it --
someone close to the mirror, talking to it -- counts as speech.
"""

import logging
import time
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 500.0
DEFAULT_SILENCE_BLOCKS = 15
DEFAULT_MIN_SPEECH_BLOCKS = 3
# 12s at HAL's 100ms blocks: plenty for one question, and in a noisy room where
# the "silence" that ends an utterance never comes, it bounds how much
# audio Whisper has to chew through (it was 30s).
DEFAULT_MAX_TOTAL_BLOCKS = 120

# Speech must be this many times louder than the background to count.
DEFAULT_NOISE_RATIO = 2.0
# 30s at HAL's 100ms blocks: longer than DEFAULT_MAX_TOTAL_BLOCKS, so even a
# maximum-length utterance can't become the "background" (the median).
NOISE_WINDOW_BLOCKS = 300
# Below this many blocks heard (1s), there's no background estimate yet: nothing counts as speech.
NOISE_WARMUP_BLOCKS = 10


def rms(block: np.ndarray) -> float:
    if len(block) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block.astype(np.float64)))))


class NoiseFloor:
    """The room's background level (median block RMS over the last 30s), shared across utterances.

    Lets capture_utterance raise its threshold to `ratio` x the background:
    distant voices, a TV, a fan... stay under it, the person at the mirror
    doesn't. In a quiet room the fixed threshold still applies.
    """

    def __init__(self, ratio: float = DEFAULT_NOISE_RATIO, window_blocks: int = NOISE_WINDOW_BLOCKS):
        self.ratio = ratio
        self._levels = deque(maxlen=window_blocks)

    def observe(self, level: float) -> None:
        self._levels.append(level)

    @property
    def level(self) -> float:
        if len(self._levels) < NOISE_WARMUP_BLOCKS:
            return 0.0
        return float(np.median(self._levels))

    def threshold(self, minimum: float) -> float:
        # Until the room has been heard for a moment, nothing counts as speech:
        # otherwise chatter at startup would be taken for someone talking.
        if len(self._levels) < NOISE_WARMUP_BLOCKS:
            return float("inf")
        return max(minimum, self.level * self.ratio)


def capture_utterance(
    audio_blocks,
    threshold: float = DEFAULT_THRESHOLD,
    silence_blocks: int = DEFAULT_SILENCE_BLOCKS,
    min_speech_blocks: int = DEFAULT_MIN_SPEECH_BLOCKS,
    max_total_blocks: int = DEFAULT_MAX_TOTAL_BLOCKS,
    deadline: float = None,
    noise_floor: NoiseFloor = None,
):
    """Consume int16 mono audio blocks from `audio_blocks` until one utterance is captured.

    An utterance starts on the first block whose RMS energy reaches
    `threshold` and ends after `silence_blocks` consecutive quiet blocks (or
    `max_total_blocks` total, as a hard cap). Silent blocks before any
    speech starts are discarded rather than counted.

    `deadline`, if given, is a `time.monotonic()` timestamp: once passed
    with no speech having started yet, this gives up and returns None
    instead of waiting forever -- used by Assistant's wake window to stop
    waiting for a follow-up question once the window's expired. An
    utterance already in progress is never cut off by the deadline; only
    the wait for the *next* one is bounded.

    `noise_floor`, if given, is fed every block and lifts `threshold` to
    its ratio x the room's background level (see NoiseFloor).

    Returns the concatenated int16 samples for one utterance, or None if
    `audio_blocks` is exhausted (relevant for finite/test iterators -- a
    live microphone stream never ends) or the deadline passed first.
    """
    blocks = []
    speech_blocks = 0
    silence_run = 0

    for block in audio_blocks:
        if not blocks and deadline is not None and time.monotonic() >= deadline:
            logger.info("VAD: deadline passed with no speech -- giving up on this utterance")
            return None

        level = rms(block)
        if noise_floor is None:
            loud = level >= threshold
        else:
            loud = level >= noise_floor.threshold(threshold)
            noise_floor.observe(level)

        if not blocks and not loud:
            continue

        blocks.append(block)
        if loud:
            speech_blocks += 1
            silence_run = 0
        else:
            silence_run += 1

        if silence_run >= silence_blocks or len(blocks) >= max_total_blocks:
            if speech_blocks >= min_speech_blocks:
                utterance = np.concatenate(blocks)
                logger.info(
                    "VAD: utterance captured (%d speech blocks, %d samples, threshold %.0f, background %.0f) "
                    "-- handing off to STT",
                    speech_blocks,
                    len(utterance),
                    threshold if noise_floor is None else noise_floor.threshold(threshold),
                    0.0 if noise_floor is None else noise_floor.level,
                )
                return utterance
            logger.debug(
                "VAD: discarding utterance shorter than min_speech_blocks (%d < %d)",
                speech_blocks,
                min_speech_blocks,
            )
            blocks, speech_blocks, silence_run = [], 0, 0

    return None
