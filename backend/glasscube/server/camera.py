"""Camera input for the server: a local camera, or one streamed from another machine on the LAN."""

import asyncio
import logging
import time

import cv2

from ..hal import is_stream_url

# A streamed camera (an http:// URL, see scripts/lan_media_server.py): how long to
# wait on opening it or on a frame before treating it as down, and how often to
# try again while it is.
STREAM_TIMEOUT_MS = 5000
STREAM_RETRY_SECONDS = 5
# Window over which the watchdog counts frames.
WATCHDOG_SECONDS = 10

logger = logging.getLogger(__name__)


class Camera:
    """Reads frames from `source`: a local camera index, or an http:// MJPEG stream.

    `is_open` and `frames_read` are there for `watch_frame_rate`.
    """

    def __init__(self, source=0):
        self.source = source
        self.is_open = False
        self.frames_read = 0

    async def run(self, on_frame, keep_running):
        """Await `on_frame(frame)` for every frame while `keep_running()` is true.

        Returns at once if a local camera can't be opened (the mirror then runs in
        data-only mode). A stream keeps being retried instead: it can be down at
        startup or drop later.
        """
        if is_stream_url(self.source):
            await self._run_stream(on_frame, keep_running)
        else:
            await self._run_local(on_frame, keep_running)

    async def _deliver(self, on_frame, frame):
        self.frames_read += 1
        await on_frame(frame)

    async def _run_local(self, on_frame, keep_running):
        capture = cv2.VideoCapture(self.source)
        if not capture.isOpened():
            capture.release()
            logger.warning("Could not open camera %s; running in data-only mode", self.source)
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)

        self.is_open = True
        try:
            while keep_running():
                ok, frame = capture.read()
                if ok:
                    await self._deliver(on_frame, frame)
                await asyncio.sleep(0.01 if ok else 0.02)
        finally:
            self.is_open = False
            capture.release()

    async def _run_stream(self, on_frame, keep_running):
        """Opening and reading run in a worker thread: a stalled stream blocks for up
        to the timeouts, and must not freeze the event loop (WebSocket clients,
        widgets) with it."""
        capture = None
        next_open_at = 0.0
        last_frame_at = 0.0
        waiting_logged = False
        try:
            while keep_running():
                now = time.time()
                if capture is None and now >= next_open_at:
                    capture = await asyncio.to_thread(self._open_stream)
                    if capture is None:
                        next_open_at = now + STREAM_RETRY_SECONDS
                        if not waiting_logged:
                            logger.warning("Stream %s not reachable; retrying every %ss", self.source, STREAM_RETRY_SECONDS)
                            waiting_logged = True
                    else:
                        logger.info("Connected to stream %s", self.source)
                        self.is_open = True
                        last_frame_at = time.time()
                        waiting_logged = False

                ok = False
                if capture is not None:
                    ok, frame = await asyncio.to_thread(capture.read)
                    if ok:
                        last_frame_at = time.time()
                        await self._deliver(on_frame, frame)
                    elif time.time() - last_frame_at > STREAM_TIMEOUT_MS / 1000:
                        logger.warning("Stream %s stopped sending frames; reconnecting", self.source)
                        self.is_open = False
                        capture.release()
                        capture = None
                        next_open_at = 0.0

                await asyncio.sleep(0.01 if ok else 0.02)
        finally:
            self.is_open = False
            if capture is not None:
                capture.release()

    def _open_stream(self):
        capture = cv2.VideoCapture(
            self.source,
            cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, STREAM_TIMEOUT_MS, cv2.CAP_PROP_READ_TIMEOUT_MSEC, STREAM_TIMEOUT_MS],
        )
        if not capture.isOpened():
            capture.release()
            return None
        return capture


async def watch_frame_rate(camera, keep_running, window=WATCHDOG_SECONDS):
    """Log the frame rate when it changes state: first frames, a stall, and recovery.

    A stall is the camera being open with no frame read for `window` seconds --
    e.g. a LAN stream that hangs without dropping, which `Camera.run` can't see.
    """
    flowing = None  # unknown until a window with the camera open
    window_start = time.time()
    last_count = camera.frames_read
    while keep_running():
        await asyncio.sleep(0.5)
        if time.time() - window_start < window:
            continue
        window_start = time.time()
        frames, last_count = camera.frames_read - last_count, camera.frames_read
        if not camera.is_open:
            flowing = None
            continue
        if frames and flowing is not True:
            logger.info("Processing %.0f frames/s", frames / window)
        elif not frames and flowing is not False:
            logger.warning("Camera open, but no frame processed in the last %ss", window)
        flowing = bool(frames)
