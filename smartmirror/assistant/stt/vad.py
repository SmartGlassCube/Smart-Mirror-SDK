"""Minimal energy-based voice activity detection for utterance segmentation.

No ML and no extra dependencies -- just an RMS threshold over int16 audio
blocks. This is what keeps STT off the hot path while the room is silent;
it is not a substitute for a real VAD model if accuracy ever matters more
than "good enough to gate an expensive call".
"""

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 500.0
DEFAULT_SILENCE_BLOCKS = 15
DEFAULT_MIN_SPEECH_BLOCKS = 3
# 12s at HAL's 100ms blocks: plenty for one question, and in a noisy room where
# the "silence" that ends an utterance never comes, it bounds how much
# audio Whisper has to chew through (it was 30s).
DEFAULT_MAX_TOTAL_BLOCKS = 120


def rms(block: np.ndarray) -> float:
    if len(block) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block.astype(np.float64)))))


def capture_utterance(
    audio_blocks,
    threshold: float = DEFAULT_THRESHOLD,
    silence_blocks: int = DEFAULT_SILENCE_BLOCKS,
    min_speech_blocks: int = DEFAULT_MIN_SPEECH_BLOCKS,
    max_total_blocks: int = DEFAULT_MAX_TOTAL_BLOCKS,
    deadline: float = None,
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

        loud = rms(block) >= threshold

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
                    "VAD: utterance captured (%d speech blocks, %d samples) -- handing off to STT",
                    speech_blocks,
                    len(utterance),
                )
                return utterance
            logger.debug(
                "VAD: discarding utterance shorter than min_speech_blocks (%d < %d)",
                speech_blocks,
                min_speech_blocks,
            )
            blocks, speech_blocks, silence_run = [], 0, 0

    return None
