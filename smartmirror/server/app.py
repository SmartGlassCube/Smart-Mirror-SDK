import asyncio
import logging
import mimetypes
import threading
import time
from http import HTTPStatus

import cv2
import websockets
from websockets.datastructures import Headers
from websockets.http11 import Response

from ..core import StateManager
from ..hal import HAL, is_stream_url
from ..vision import GestureDetector
from .camera_preview import CameraPreview
from .frontend_launcher import FrontendLauncher
from .hand_pointer import HandPointer
from .websocket import ClientHub
from .widget_data import refresh_widget_data

# The events' uploaded images (content sync's local copies) are served over plain
# HTTP on the WebSocket port, under this path.
CONTENT_IMAGES_PATH = "/content-images"

# A camera streamed over the LAN (camera_id is an http:// URL): how long to
# wait on opening it or on a frame before treating it as down, and how often
# to try again while it is.
CAMERA_STREAM_TIMEOUT_MS = 5000
CAMERA_STREAM_RETRY_SECONDS = 5

logger = logging.getLogger(__name__)


class SmartMirrorServer:
    """Runs the mirror: camera -> GestureDetector -> StateManager -> WebSocket -> frontend.

    Pass either a `graph` (pages + edges) or a configured `state_manager`.
    Pass a `gesture_detector` to customise the gesture set.
    Pass an `assistant` built with `stt=True` to run the voice chatbot alongside,
    shown by the Abdo avatar in the frontend.
    """

    def __init__(
        self,
        graph=None,
        state_manager=None,
        gesture_detector=None,
        with_camera=True,
        camera_id=0,
        camera_preview=True,
        camera_preview_fps=10,
        camera_preview_width=240,
        pointer_hand="right",
        ws_host="localhost",
        ws_port=8080,
        with_frontend=True,
        frontend_dir=None,
        frontend_host="localhost",
        frontend_port=5173,
        hardware=None,
        assistant=None,
        content_sync=None,
        widget_update_tick=0.5,
    ):
        if state_manager is None:
            state_manager = StateManager(graph=graph)
        elif graph is not None:
            state_manager.set_graph(graph)

        self.state_manager = state_manager
        self.gesture_detector = gesture_detector
        self.with_camera = with_camera
        self.camera_id = camera_id
        # Small annotated webcam view (+ latest gestures) in the frontend's top-right corner.
        self.camera_preview = (
            CameraPreview(fps=camera_preview_fps, width=camera_preview_width) if camera_preview else None
        )
        # Cursor following this hand's index fingertip ("left", "right", or None to hide it).
        self.hand_pointer = HandPointer(hand=pointer_hand) if pointer_hand else None
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.frontend = (
            FrontendLauncher(frontend_dir=frontend_dir, host=frontend_host, port=frontend_port, ws_port=ws_port)
            if with_frontend
            else None
        )
        # One HAL for the whole app; the assistant's own when it brings one.
        self.hardware = hardware or getattr(assistant, "hal", None) or HAL()
        self.assistant = assistant
        # Opt-in Mongo content sync (smartmirror.content) -- None (default)
        # means the mirror behaves exactly as before. See examples/mvp.py.
        self.content_sync = content_sync
        if content_sync is not None:
            content_sync.image_base_url = f"http://{ws_host}:{ws_port}{CONTENT_IMAGES_PATH}"
        # Stops the background loops (content sync, voice assistant).
        self._stop_event = threading.Event()

        self.widget_update_tick = widget_update_tick
        self.hub = ClientHub(state_manager)
        self.running = False

    async def run(self):
        print(f"[Server] WebSocket server on ws://{self.ws_host}:{self.ws_port}")
        self.running = True
        try:
            async with websockets.serve(
                self.hub.handle_client, self.ws_host, self.ws_port, process_request=self._serve_content_image
            ):
                if self.frontend is not None:
                    await self.frontend.start()
                tasks = [self._main_loop()]
                if self.content_sync is not None:
                    tasks.append(self._content_sync_loop())
                if getattr(self.assistant, "stt", None) is not None:
                    tasks.append(self._assistant_loop())
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._stop_background_loops()
            if self.frontend is not None:
                await self.frontend.stop()

    def _serve_content_image(self, connection, request):
        """GET /content-images/<file>: an event image. Any other request goes on to the WebSocket handshake."""
        path = request.path.split("?", 1)[0]
        if not path.startswith(CONTENT_IMAGES_PATH + "/"):
            return None
        name = path[len(CONTENT_IMAGES_PATH) + 1:]
        file = self.content_sync.images_dir / name if self.content_sync is not None else None
        if file is None or "/" in name or name.startswith(".") or not file.is_file():
            return connection.respond(HTTPStatus.NOT_FOUND, "Not found\n")
        body = file.read_bytes()
        headers = Headers({
            "Content-Type": mimetypes.guess_type(name)[0] or "application/octet-stream",
            "Content-Length": str(len(body)),
            "Cache-Control": "max-age=86400",
        })
        return Response(HTTPStatus.OK, "OK", headers, body)

    async def _content_sync_loop(self):
        try:
            await self.content_sync.run_forever(
                current_page_getter=lambda: self.state_manager.current_node_id,
                stop_event=self._stop_event,
            )
        except Exception:
            logger.exception("Content sync loop failed")

    async def _assistant_loop(self):
        # As soon as a question is heard the frontend shows its transcript and Abdo wakes
        # (he's "thinking" while the LLM answers), then he types the answer while TTS speaks it.
        try:
            await self.assistant.listen_loop(
                hal=self.hardware,
                on_question=self._on_assistant_question,
                on_answer=self.assistant_say,
                stop_event=self._stop_event,
            )
        except Exception:
            logger.exception("Assistant loop failed")

    def _on_assistant_question(self, question):
        self.assistant_heard(question)
        self.assistant_wake()

    def stop(self):
        self.running = False
        self._stop_background_loops()

    def _stop_background_loops(self):
        self._stop_event.set()
        # Ends the mic stream, so a voice turn blocked waiting for speech returns.
        close = getattr(self.hardware, "close", None)
        if callable(close):
            close()

    # Hooks for the voice chatbot (RAG), shown by the Abdo avatar in the frontend.
    def assistant_wake(self):
        """Someone started talking to the chatbot: wake Abdo."""
        self.hub.broadcast({"type": "ASSISTANT_WAKE"})

    def assistant_heard(self, text):
        """Show what the chatbot heard next to the camera preview ("" = only the wake word)."""
        self.hub.broadcast({"type": "ASSISTANT_HEARD", "text": text})

    def assistant_say(self, text):
        """Show a chatbot reply, typed out in Abdo's speech bubble."""
        self.hub.broadcast({"type": "ASSISTANT_SAY", "text": text})

    async def _main_loop(self):
        if self.with_camera and is_stream_url(self.camera_id):
            return await self._network_camera_loop()

        capture = self._open_camera() if self.with_camera else None
        if capture is None:
            while self.running:
                await self._refresh_widget_data()
                await asyncio.sleep(self.widget_update_tick)
            return

        if self.gesture_detector is None:
            self.gesture_detector = GestureDetector()

        last_widget_refresh = 0.0
        try:
            while self.running:
                ok, frame = capture.read()
                if ok:
                    await self._process_frame(frame)

                now = time.time()
                if now - last_widget_refresh >= self.widget_update_tick:
                    await self._refresh_widget_data()
                    last_widget_refresh = now

                await asyncio.sleep(0.01 if ok else 0.02)
        finally:
            capture.release()
            self.gesture_detector.close()

    def _open_camera(self):
        capture = cv2.VideoCapture(self.camera_id)
        if not capture.isOpened():
            print(f"[Camera] Could not open camera {self.camera_id}; running in data-only mode")
            return None
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)
        return capture

    async def _network_camera_loop(self):
        """_main_loop for a camera streamed from another machine (camera_id is an http:// URL).

        Unlike a local camera, the stream can be down at startup or drop
        later, so this keeps retrying instead of settling into data-only
        mode -- widgets stay live meanwhile. Opening and reading run in a
        worker thread: a stalled stream blocks for up to the timeouts, and
        must not freeze the event loop (WebSocket clients, widgets) with it.
        """
        if self.gesture_detector is None:
            self.gesture_detector = GestureDetector()

        capture = None
        next_open_at = 0.0
        last_frame_at = 0.0
        last_widget_refresh = 0.0
        waiting_logged = False
        try:
            while self.running:
                now = time.time()
                if capture is None and now >= next_open_at:
                    capture = await asyncio.to_thread(self._open_network_camera)
                    if capture is None:
                        next_open_at = now + CAMERA_STREAM_RETRY_SECONDS
                        if not waiting_logged:
                            print(f"[Camera] Stream {self.camera_id} not reachable; retrying every {CAMERA_STREAM_RETRY_SECONDS}s")
                            waiting_logged = True
                    else:
                        print(f"[Camera] Connected to stream {self.camera_id}")
                        last_frame_at = time.time()
                        waiting_logged = False

                ok = False
                if capture is not None:
                    ok, frame = await asyncio.to_thread(capture.read)
                    if ok:
                        last_frame_at = time.time()
                        await self._process_frame(frame)
                    elif time.time() - last_frame_at > CAMERA_STREAM_TIMEOUT_MS / 1000:
                        print(f"[Camera] Stream {self.camera_id} stopped sending frames; reconnecting")
                        capture.release()
                        capture = None
                        next_open_at = 0.0

                now = time.time()
                if now - last_widget_refresh >= self.widget_update_tick:
                    await self._refresh_widget_data()
                    last_widget_refresh = now

                await asyncio.sleep(0.01 if ok else 0.02)
        finally:
            if capture is not None:
                capture.release()
            self.gesture_detector.close()

    def _open_network_camera(self):
        capture = cv2.VideoCapture(
            self.camera_id,
            cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_STREAM_TIMEOUT_MS, cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAMERA_STREAM_TIMEOUT_MS],
        )
        if not capture.isOpened():
            capture.release()
            return None
        return capture

    async def _process_frame(self, frame):
        frame = cv2.flip(frame, 1)  # mirror, so the user's left is screen-left
        # The debug window draws on `frame` in place; keep the preview's copy clean.
        clean_frame = frame.copy() if self.gesture_detector.debug else frame
        result = self.gesture_detector.process_frame(frame)

        if self.state_manager.handle_gesture_events(events=result["events"], signals=result["signals"]):
            self.hub.broadcast_state()

        if self.hand_pointer is not None and self.hub.clients:
            message = self.hand_pointer.message(result["signals"])
            if message is not None:
                self.hub.broadcast(message)

        if self.camera_preview is not None and self.hub.clients:
            message = self.camera_preview.message(clean_frame, result, time.time())
            if message is not None:
                self.hub.broadcast(message)

        # The debug window needs waitKey to repaint; `q` stops the server.
        if self.gesture_detector.debug and cv2.waitKey(1) & 0xFF == ord("q"):
            self.stop()

    async def _refresh_widget_data(self):
        if await refresh_widget_data(self.state_manager.get_current_widgets()):
            self.hub.broadcast_state()
