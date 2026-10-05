# Phase 2 acceptance check: voice pipeline

Audio I/O can't be meaningfully unit-tested end-to-end (no real mic/speaker
in CI), so this is a manual check. `pytest` already covers the VAD,
wake-word matching, STT, TTS, and HAL logic in isolation with fake/mocked
audio -- this is about confirming the whole thing works together on real
hardware, without regressing gesture navigation.

## Setup

1. Install the assistant extras: `pip install -e ".[assistant]"`
2. Start a local LLM server and pull a small model (mvp.py defaults to
   this so no paid API key is needed):
   ```
   ollama serve &
   ollama pull qwen2.5:0.5b
   ```
   Using a different endpoint instead? Set `SMARTMIRROR_LLM_API_KEY`,
   `SMARTMIRROR_LLM_BASE_URL`, `SMARTMIRROR_LLM_MODEL` before running mvp.py.
3. Download a Piper voice (TTS is enabled by default in mvp.py):
   ```
   python -m piper.download_voices en_US-lessac-medium \
     --download-dir ~/.local/share/smartmirror/piper_voices
   ```
   (Skipping this is fine too -- PiperTTS.speak() raises a clear error
   naming the exact command above instead of failing silently, but the
   loop will crash instead of just staying silent, so it's worth doing.)
4. Make sure a microphone and speakers are connected and are the system
   default input/output device (`python -c "import sounddevice as sd;
   print(sd.query_devices())"` to check).

## Run

```
python examples/mvp.py
```

Watch the terminal for `[Server] Starting Smart Mirror Backend`, then open
the UI (default `http://localhost:5173`) to see the mirror canvas,
including the new assistant widget near the bottom-left with the prompt
`Say "ABDOU, <question>" to ask the assistant.`

## What to verify

1. **Gesture nav still works, unaffected.** Swipe/gesture between the
   `home` and `focus` pages as before -- this should feel identical to
   pre-Phase-2 behavior. This is the regression check: voice runs
   concurrently via `asyncio.gather`, so it must never stall or block
   camera_loop.
2. **Wake word + question.** Say clearly: **"ABDOU, what is IEEE INSAT?"**
   (a question the seed corpus can answer). Expect, within a few seconds,
   in the terminal (see "Reading the logs" below for what each line means):
   ```
   smartmirror.assistant.stt.wake_word INFO Listening for wake word 'abdou'...
   smartmirror.assistant.stt.vad INFO VAD: utterance captured (... speech blocks, ... samples) -- handing off to STT
   smartmirror.assistant.stt.whisper INFO Whisper transcript: 'Abdu, what is IEEE INSAT?'
   smartmirror.assistant.stt.wake_word INFO Wake word check: heard '...', comparing 'abdu' to 'abdou' -- similarity=0.89 -- MATCH
   smartmirror.assistant.assistant INFO Answering question: 'what is IEEE INSAT?'
   smartmirror.assistant.assistant INFO Answer: '...'
   ```
   Plus:
   - Spoken reply through the speakers (Piper TTS), grounded in the seed
     corpus (not a generic/hallucinated answer).
   - The UI's assistant widget updates to `You: what is IEEE INSAT? /
     Assistant: <the answer>` -- confirms the STATE_UPDATE broadcast path.
3. **Ignores non-wake speech.** Say something without "ABDOU" first (e.g.
   "turn on the lights") -- nothing should happen; the assistant keeps
   listening silently (check `capture_utterance`/`WakeWordDetector` logic
   isn't triggering full chat calls on every utterance).
4. **Loop continues.** After one exchange, say the wake phrase again with
   a different question -- it should answer again without restarting the
   app.
5. **Wake window (follow-up questions without "ABDOU").** Right after step
   2's answer, ask a follow-up *without* the wake word (e.g. "and what
   events do they run?") -- it should still answer, and the terminal should
   show `Wake window open until HH:MM:SS, no wake word needed`. Wait past
   that time without speaking, then ask another question without the wake
   word -- it should be ignored, and the terminal should show
   `Wake window closed, listening for 'abdou' again` before your next
   `"ABDOU, ..."` gets picked up. Default window is 3 minutes
   (`Assistant(wake_window_seconds=...)` to change it, or `0`/`None` to
   disable the feature and always require the wake word).

## Reading the logs

mvp.py configures logging so `smartmirror.*` shows at INFO while noisy
third-party libraries (httpx, sentence_transformers, ...) stay at WARNING.
Four checkpoints to watch for on every turn, in order:

1. `wake_word ... Listening for wake word 'abdou'...` -- confirms the loop
   is alive and actually waiting on the mic, not stuck or silently dead.
2. `vad ... VAD: utterance captured (...)` -- the energy-based VAD decided
   someone spoke, *before* the (comparatively expensive) Whisper call runs.
   If you talk and never see this, the mic input or VAD threshold is the
   problem, not STT or the LLM.
3. `whisper ... Whisper transcript: '...'` -- the raw ASR output, logged
   for *every* utterance, not just ones that match the wake word. If your
   wake-word attempts keep failing, this is what tells you whether Whisper
   even heard you right (garbled audio/mic issue) or heard you fine but the
   fuzzy match rejected it (see the `wake_word` line's `similarity=` score).
4. `wake_word ... Wake word check: ... -- MATCH` or `-- no match` -- states
   the verdict explicitly, against exactly what text.

whisper.cpp itself also prints its own native (non-Python-logging) lines
like `whisper_model_load: ...` directly to stderr -- unrelated noise from
the C++ library, not something these `logging` changes control.

## Crash resilience

Two different failure classes, two different mitigations:

- **Ordinary Python exceptions** (an LLM API hiccup, a transient error) are
  now caught per-turn in `Assistant.listen_loop` and per-frame in
  `camera_loop`, logged (`ERROR`, with traceback), and the loop moves on
  instead of dying. `SmartMirrorServer.run()` also runs `camera_loop` and
  `assistant_loop` with `asyncio.gather(..., return_exceptions=True)`, so
  even if one loop *does* exit on an unhandled exception, the other keeps
  running instead of both being cancelled together. Covered by
  `test/test_smartmirror_server.py` and
  `smartmirror/assistant/tests/test_assistant.py`.
- **Native-library segfaults** (a `Segmentation fault (core dumped)`, as
  reported during Phase 2 review, once, non-reproducible) are a different
  problem: they kill the whole Python process below where any Python
  `try/except` can react, gather included. Camera (mediapipe/XNNPACK,
  main thread), mic capture (PortAudio/ALSA) and STT (whisper.cpp, both on
  a worker thread) all run their own native thread pools concurrently under
  asyncio -- plausible contributing factors, but there's no traceback or
  core dump from that one occurrence to point at a specific line, so this
  isn't a fixed root cause. What's actually done about it:
  - `WhisperSTT` now caps whisper.cpp to `n_threads=2` by default (was
    "up to 4") to reduce contention with mediapipe's own thread pool on a
    constrained Pi. Override via `WhisperSTT(n_threads=...)`.
  - The GUI debug window (`cv2.imshow`, a separate, known crash-prone
    surface when mixed with other threads) is off by default
    (`GestureDetector(debug=False)`) and wasn't enabled in this session,
    so it's an unlikely culprit here -- but avoid turning it on in a
    long-running/Pi deployment.
  - Since a segfault can't be caught in-process, use
    `scripts/run_mvp_supervised.sh` instead of running `examples/mvp.py`
    directly for anything long-running: it restarts on any crash
    (segfault included), logs every restart with a timestamp, and gives up
    loudly instead of restart-looping forever if crashes are frequent. On
    a permanent Pi install, a systemd unit with `Restart=on-failure` is
    the more standard equivalent.
  - If a segfault recurs, the next debugging step is a core dump/`gdb`
    backtrace from the actual crash, or running STT in a separate OS
    process (not just a thread) so it can't take mediapipe down with it --
    flagged as a Phase 3 item, not attempted here without a reproducible
    case to diagnose against.

## Known limitations to expect, not bugs

- Small/local Whisper models (mvp.py's default) sometimes mis-transcribe
  "ABDOU" (e.g. as "Abdu") and acronyms like "IEEE INSAT" -- the wake-word
  match is deliberately fuzzy to tolerate this, but a garbled question can
  still lead retrieval astray. Bigger `WhisperSTT(model=...)` improves this
  at the cost of latency.
- The seed corpus is 3 placeholder files (tracked follow-up issue); answers
  outside that content may not be grounded.
- No barge-in or multi-turn conversation -- one wake phrase = one question
  = one answer, out of scope for Phase 2.

## No hardware handy? `scripts/voice_pipeline_synthetic_check.py`

Synthesizes "ABDOU, what is IEEE INSAT?" with Piper, feeds it through the
same VAD -> WhisperSTT -> WakeWordDetector -> Assistant.chat() path a real
mic would, and prints the transcript + grounded answer. Not a substitute
for the real-hardware run above (no HAL/sounddevice involved), but a fast
way to confirm the pipeline logic end-to-end after a code change:

```
python scripts/voice_pipeline_synthetic_check.py
```
