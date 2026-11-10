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
from ..hal import HAL
from ..vision import GestureDetector
from .camera import Camera, watch_frame_rate
from .camera_preview import CameraPreview
from .hand_pointer import HandPointer
from .websocket import ClientHub
from .widget_data import refresh_widget_data

# The events' uploaded images (content sync's local copies) are served over plain
# HTTP on the WebSocket port, under this path.
CONTENT_IMAGES_PATH = "/content-images"

logger = logging.getLogger(__name__)


class SmartMirrorServer:
    """Runs the mirror: camera -> GestureDetector -> StateManager -> WebSocket -> frontend.

    Pass either a `graph` (pages + edges) or a configured `state_manager`.
    Pass a `gesture_detector` to customise the gesture set.
    Pass an `assistant` built with `stt=True` to run the voice chatbot alongside,
    shown by the Abdo avatar in the frontend.

    The frontend is a separate app that connects to `ws://<ws_host>:<ws_port>`
    (see docs/protocol.md); this server doesn't start it.
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
        self.gesture_detector = gesture_detector  # created on the first frame when None
        # A local camera index, or an http:// URL served by scripts/lan_media_server.py.
        self.camera = Camera(camera_id) if with_camera else None
        # Small annotated webcam view (+ latest gestures) in the frontend's top-right corner.
        self.camera_preview = (
            CameraPreview(fps=camera_preview_fps, width=camera_preview_width) if camera_preview else None
        )
        # Cursor following this hand's index fingertip ("left", "right", or None to hide it).
        self.hand_pointer = HandPointer(hand=pointer_hand) if pointer_hand else None
        self.ws_host = ws_host
        self.ws_port = ws_port
        # One HAL for the whole app; the assistant's own when it brings one.
        self.hardware = hardware or getattr(assistant, "hal", None) or HAL()
        self.assistant = assistant
        # Opt-in Mongo content sync (smartmirror.content); None leaves it out.
        self.content_sync = content_sync
        if content_sync is not None:
            content_sync.image_base_url = f"http://{ws_host}:{ws_port}{CONTENT_IMAGES_PATH}"
        # Stops the background loops (content sync, voice assistant).
        self._stop_event = threading.Event()

        self.widget_update_tick = widget_update_tick
        self.hub = ClientHub(state_manager)
        self.running = False

    async def run(self):
        self.running = True
        try:
            async with websockets.serve(
                self.hub.handle_client, self.ws_host, self.ws_port, process_request=self._serve_content_image
            ):
                logger.info("WebSocket server on ws://%s:%s", self.ws_host, self.ws_port)
                tasks = [
                    self._log_crash("Camera loop", self._main_loop()),
                    self._log_crash("Widget data loop", self._widget_data_loop()),
                ]
                if self.camera is not None:
                    tasks.append(self._log_crash("Camera watchdog", watch_frame_rate(self.camera, lambda: self.running)))
                if self.content_sync is not None:
                    tasks.append(self._log_crash("Content sync loop", self._content_sync_loop()))
                if getattr(self.assistant, "stt", None) is not None:
                    tasks.append(self._log_crash("Assistant loop", self._assistant_loop()))
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._stop_background_loops()

    def stop(self):
        self.running = False
        self._stop_background_loops()

    def _stop_background_loops(self):
        self._stop_event.set()
        # Ends the mic stream, so a voice turn blocked waiting for speech returns.
        close = getattr(self.hardware, "close", None)
        if callable(close):
            close()

    async def _log_crash(self, name, loop):
        """Run one of run()'s loops, logging a crash right away -- gather(return_exceptions=True) would hide it."""
        try:
            await loop
        except Exception:
            logger.exception("%s crashed", name)

    # -- background loops ------------------------------------------------------

    async def _main_loop(self):
        """Camera frames -> gestures -> state. Without a camera, the widget data loop keeps the mirror live."""
        if self.camera is None:
            return
        try:
            await self.camera.run(self._process_frame, lambda: self.running)
        finally:
            if self.gesture_detector is not None:
                self.gesture_detector.close()

    async def _widget_data_loop(self):
        """Keeps widget data fresh on its own schedule, so a slow or stalled camera can't hold it back."""
        while self.running:
            await self._refresh_widget_data()
            await asyncio.sleep(self.widget_update_tick)

    async def _content_sync_loop(self):
        await self.content_sync.run_forever(
            current_page_getter=lambda: self.state_manager.current_node_id,
            stop_event=self._stop_event,
        )

    async def _assistant_loop(self):
        # As soon as a question is heard the frontend shows its transcript and Abdo wakes
        # (he's "thinking" while the LLM answers), then he types the answer while TTS speaks it.
        await self.assistant.listen_loop(
            hal=self.hardware,
            on_question=self._on_assistant_question,
            on_answer=self.assistant_say,
            stop_event=self._stop_event,
        )

    # -- per-frame work ----------------------------------------------------------

    async def _process_frame(self, frame):
        if self.gesture_detector is None:
            self.gesture_detector = GestureDetector()

        frame = cv2.flip(frame, 1)  # mirror, so the user's left is screen-left
        # The debug window draws on `frame` in place; keep the preview's copy clean.
        clean_frame = frame.copy() if self.gesture_detector.debug else frame
        result = self.gesture_detector.process_frame(frame)

        if self.state_manager.handle_gesture_events(events=result["events"], signals=result["signals"]):
            self.hub.broadcast_state()

        if self.hand_pointer is not None and self.hub.clients:
            message = self.hand_pointer.message(result["signals"], result["hands"])
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

    # -- HTTP: event images --------------------------------------------------------

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

    # -- voice assistant hooks (shown by the Abdo avatar in the frontend) -------------

    def _on_assistant_question(self, question):
        self.assistant_heard(question)
        self.assistant_wake()

    def assistant_wake(self):
        """Someone started talking to the chatbot: wake Abdo."""
        self.hub.broadcast({"type": "ASSISTANT_WAKE"})

    def assistant_heard(self, text):
        """Show what the chatbot heard next to the camera preview ("" = only the wake word)."""
        self.hub.broadcast({"type": "ASSISTANT_HEARD", "text": text})

    def assistant_say(self, text):
        """Show a chatbot reply, typed out in Abdo's speech bubble."""
        self.hub.broadcast({"type": "ASSISTANT_SAY", "text": text})
