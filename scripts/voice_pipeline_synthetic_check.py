#!/usr/bin/env python3
"""Synthetic, no-hardware check of the voice pipeline.

Audio I/O can't be meaningfully unit-tested end-to-end, and not every dev
machine has a mic handy. This synthesizes "ABDOU, what is IEEE INSAT?"
with Piper, feeds the resulting audio through the same VAD -> WhisperSTT ->
WakeWordDetector -> Assistant.chat() path a real HAL.read_audio() stream
would, and prints the transcript + grounded answer. It's a fast way to
confirm the pipeline logic after a code change -- see
scripts/voice_pipeline_manual_test.md for the real-hardware acceptance
check this doesn't replace.

Requires a real LLM endpoint and a downloaded Piper voice -- see the setup
steps in voice_pipeline_manual_test.md.
"""

import io
import logging
import os
import sys
import wave
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s %(message)s")
logging.getLogger("smartmirror").setLevel(logging.INFO)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartmirror.assistant import Assistant
from smartmirror.assistant.llm import OpenAICompatBackend
from smartmirror.assistant.tts import DEFAULT_VOICE, DEFAULT_VOICES_DIR

SEED_CORPUS = Path(__file__).resolve().parents[1] / "smartmirror" / "assistant" / "rag" / "seed_corpus"
PHRASE = "ABDOU, what is IEEE INSAT?"
BLOCKSIZE = 1600  # 100ms @ 16kHz, matches HAL's default


def synthesize_phrase() -> tuple[np.ndarray, int]:
    from piper import PiperVoice

    onnx_path = os.path.join(DEFAULT_VOICES_DIR, f"{DEFAULT_VOICE}.onnx")
    config_path = f"{onnx_path}.json"
    if not os.path.exists(onnx_path):
        print(
            f"Piper voice not found. Download it first: "
            f"python -m piper.download_voices {DEFAULT_VOICE} --download-dir {DEFAULT_VOICES_DIR}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    voice = PiperVoice.load(onnx_path, config_path)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(PHRASE, wav_file)
    buffer.seek(0)

    with wave.open(buffer, "rb") as wav_file:
        samplerate = wav_file.getframerate()
        raw = wav_file.readframes(wav_file.getnframes())
    return np.frombuffer(raw, dtype=np.int16), samplerate


def resample_to_16k(samples: np.ndarray, from_rate: int) -> np.ndarray:
    if from_rate == 16000:
        return samples
    duration = len(samples) / from_rate
    x_old = np.linspace(0, duration, num=len(samples), endpoint=False)
    x_new = np.linspace(0, duration, num=int(round(duration * 16000)), endpoint=False)
    return np.interp(x_new, x_old, samples.astype(np.float32)).astype(np.int16)


class SyntheticHAL:
    """Feeds pre-recorded audio through read_audio() like a real HAL would,
    followed by enough trailing silence for the VAD to end the utterance."""

    def __init__(self, samples: np.ndarray):
        blocks = [samples[i : i + BLOCKSIZE] for i in range(0, len(samples), BLOCKSIZE)]
        blocks += [np.zeros(BLOCKSIZE, dtype=np.int16)] * 20
        self._blocks = blocks

    def read_audio(self):
        return iter(self._blocks)


def main():
    api_key = os.getenv("SMARTMIRROR_LLM_API_KEY", "ollama")
    base_url = os.getenv("SMARTMIRROR_LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.getenv("SMARTMIRROR_LLM_MODEL", "qwen2.5:0.5b")

    print(f"Synthesizing: {PHRASE!r}")
    samples, samplerate = synthesize_phrase()
    samples_16k = resample_to_16k(samples, samplerate)

    backend = OpenAICompatBackend(api_key=api_key, base_url=base_url, model=model)
    assistant = Assistant(
        llm=backend,
        documents=str(SEED_CORPUS),
        stt=True,
        tts=False,
        hal=SyntheticHAL(samples_16k),
    )

    question, answer = assistant._voice_turn()
    print(f"Wake word matched. Question heard: {question!r}")
    print(f"Answer: {answer}")


if __name__ == "__main__":
    main()
