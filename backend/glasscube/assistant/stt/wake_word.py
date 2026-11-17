"""Wake-word gating for the voice pipeline.

A dedicated keyword-spotting engine (Porcupine, openWakeWord) would need
either a paid access key or a model trained specifically on "ABDOU",
neither of which is available here -- see the phase 3 notes. Instead: the
zero-cost VAD in `vad.py` segments the mic stream into utterances while the
room is silent, and only a captured utterance is ever handed to Whisper.
That satisfies the actual goal (don't transcribe continuously) at the cost
of one Whisper pass per utterance rather than a dedicated low-power
spotter -- fine for phase 2, worth revisiting if latency/CPU matters later.
"""

import difflib
import logging
import re

from .vad import capture_utterance

logger = logging.getLogger(__name__)

DEFAULT_WAKE_WORD = "abdou"
DEFAULT_SIMILARITY_THRESHOLD = 0.6
# 1- and 2-word sliding windows: whisper sometimes splits "ABDOU" across two
# tokens (e.g. "and do", "add two"), and the wake word isn't always word[0]
# -- see _match_wake_word's docstring for the false-positive tradeoff this
# threshold was picked against.
MAX_WINDOW_SIZE = 2

# Known ASR mishearings of "abdou", collected from real transcription logs
# (base.en). The b/d plosives get dropped or softened by small models; the
# vowel/syllable skeleton (a stressed syllable + an "oo"/"oh"/"air"-ish
# trailing sound) survives. Several of these score well *below* the fuzzy
# threshold above in raw character-ratio terms (e.g. "up there" -> "upthere"
# vs "abdou" is 0.167) despite being phonetically close -- no single
# threshold catches them without also catching unrelated words, so they're
# matched as instant, exact (case/punctuation-insensitive) hits instead.
# Extend this set as more mishearings turn up in testing; it isn't
# hardcoded inline in the matching logic for exactly that reason.
WAKE_WORD_VARIANTS = {
    "abdou",
    "ado",
    "updo",
    "appdo",
    "up to",
    "add two",
    "up through",
    "up there",
    "and do",
}


class WakeWordDetector:
    """Blocks on a mic stream until an utterance starting with the wake word is heard."""

    def __init__(
        self,
        stt,
        wake_word: str = DEFAULT_WAKE_WORD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        variants: set = None,
        vad_kwargs: dict = None,
    ):
        self.stt = stt
        self.wake_word = wake_word.lower()
        self.similarity_threshold = similarity_threshold
        # The default variants are "abdou"-specific mishearings; only wire
        # them in automatically when that's actually the configured wake
        # word, so a custom wake_word doesn't inherit irrelevant variants.
        if variants is not None:
            self.variants = variants
        elif self.wake_word == DEFAULT_WAKE_WORD:
            self.variants = WAKE_WORD_VARIANTS
        else:
            self.variants = set()
        self.vad_kwargs = vad_kwargs or {}

    def listen_for_wake_word(self, audio_blocks) -> str:
        """Consume utterances from `audio_blocks` until one starts with the wake word.

        Returns whatever text followed the wake word (may be empty if the
        speaker only said the wake word itself). Non-matching utterances are
        silently discarded and listening continues.
        """
        logger.info("Listening for wake word %r...", self.wake_word)
        while True:
            audio = capture_utterance(audio_blocks, **self.vad_kwargs)
            if audio is None:
                logger.info("Audio stream ended before the wake word was heard")
                return ""  # audio_blocks exhausted -- only happens with finite/test iterators

            transcript = self.stt.transcribe(audio)
            remainder = self._match_wake_word(transcript)
            if remainder is not None:
                return remainder
            logger.info("Listening for wake word %r again...", self.wake_word)

    def _match_wake_word(self, transcript: str):
        """Return the text after the wake word, or None if it wasn't heard.

        Two layers, checked in order:

        1. Exact known-variant match against self.variants (see
           WAKE_WORD_VARIANTS): case/punctuation-insensitive, no scoring.
           Several real mishearings of "ABDOU" -- the b/d plosives get
           dropped or softened by small models, leaving just the vowel
           skeleton -- score far too low in character-ratio terms to ever
           clear a fuzzy threshold (e.g. "up there" -> "upthere" vs "abdou"
           is 0.167), so they're matched as instant hits instead of tuning
           a threshold that can't separate them from unrelated words.
        2. Fuzzy fallback (only reached if no variant matched): scans every
           1- and 2-word window at every position and fuzzy-matches each
           against the wake word, taking the best-scoring one, instead of
           only ever checking transcript.split()[0].

        similarity_threshold (layer 2) is intentionally still 0.6, not
        lowered to catch short fragments like "add"/"and"/"do" alone
        (~0.50-0.57 against "abdou"): those scores are *lower* than common
        English words this must not false-trigger on -- "about" scores
        0.80, "radio"/"above" score 0.60 -- so a threshold low enough to
        accept the fragments would also make ordinary sentences containing
        those words wake the assistant.
        """
        words = transcript.strip().split()
        if not words:
            logger.info("Wake word check: empty transcript, no match")
            return None

        normalized = [re.sub(r"[^a-zA-Z]", "", word).lower() for word in words]

        variant_match = self._match_known_variant(normalized)
        if variant_match is not None:
            end, variant = variant_match
            logger.info(
                "Wake word check: heard %r, matched known variant %r [exact-variant] -- MATCH",
                transcript,
                variant,
            )
            return " ".join(words[end:]).strip(" ,:-")

        best_score = -1.0
        best_end = None
        best_candidate = None
        for start in range(len(words)):
            for size in range(1, MAX_WINDOW_SIZE + 1):
                end = start + size
                if end > len(words):
                    continue
                candidate = "".join(normalized[start:end])
                if not candidate:
                    continue
                score = difflib.SequenceMatcher(None, candidate, self.wake_word).ratio()
                if score > best_score:
                    best_score, best_end, best_candidate = score, end, candidate

        matched = best_score >= self.similarity_threshold

        logger.info(
            "Wake word check: heard %r, comparing %r to %r -- similarity=%.2f -- %s [fuzzy]",
            transcript,
            best_candidate,
            self.wake_word,
            best_score,
            "MATCH" if matched else "no match",
        )

        if not matched:
            return None

        return " ".join(words[best_end:]).strip(" ,:-")

    def _match_known_variant(self, normalized_words: list):
        """Scan every position for an exact hit against self.variants.

        Returns (end_index, variant) for the first match found, or None.
        Multi-word variants (e.g. "up to") must appear as consecutive
        words, not just both be present somewhere in the transcript.
        """
        for start in range(len(normalized_words)):
            for variant in self.variants:
                variant_words = variant.split()
                end = start + len(variant_words)
                if end > len(normalized_words):
                    continue
                if normalized_words[start:end] == variant_words:
                    return end, variant
        return None
