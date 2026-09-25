import asyncio
import time

import cv2
import websockets

from ..core import StateManager
from ..hal import HAL
from ..vision import GestureDetector
from .frontend_launcher import FrontendLauncher
from .websocket import ClientHub
from .widget_data import refresh_widget_data


class SmartMirrorServer:
    """Runs the mirror: camera -> GestureDetector -> StateManager -> WebSocket -> frontend.

    Pass either a `graph` (pages + edges) or a configured `state_manager`.
    Pass a `gesture_detector` to customise the gesture set.
    """

    def __init__(
        self,
        graph=None,
        state_manager=None,
        gesture_detector=None,
        with_camera=True,
        camera_id=0,
        ws_host="localhost",
        ws_port=8080,
        with_frontend=True,
        frontend_dir=None,
        frontend_host="localhost",
        frontend_port=5173,
        hardware=None,
        assistant=None,
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
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.frontend = (
            FrontendLauncher(frontend_dir=frontend_dir, host=frontend_host, port=frontend_port, ws_port=ws_port)
            if with_frontend
            else None
        )
        # Reserved for upcoming hardware / voice-assistant integrations.
        self.hardware = hardware or HAL()
        self.assistant = assistant

        self.widget_update_tick = widget_update_tick
        self.hub = ClientHub(state_manager)
        self.running = False

    async def run(self):
        print(f"[Server] WebSocket server on ws://{self.ws_host}:{self.ws_port}")
        self.running = True
        try:
            async with websockets.serve(self.hub.handle_client, self.ws_host, self.ws_port):
                if self.frontend is not None:
                    await self.frontend.start()
                await self._main_loop()
        finally:
            if self.frontend is not None:
                await self.frontend.stop()

    def stop(self):
        self.running = False

    async def _main_loop(self):
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

    async def _process_frame(self, frame):
        frame = cv2.flip(frame, 1)  # mirror, so the user's left is screen-left
        result = self.gesture_detector.process_frame(frame)

        if self.state_manager.handle_gesture_events(events=result["events"], signals=result["signals"]):
            self.hub.broadcast_state()

        # The debug window needs waitKey to repaint; `q` stops the server.
        if self.gesture_detector.debug and cv2.waitKey(1) & 0xFF == ord("q"):
            self.stop()

    async def _refresh_widget_data(self):
        if await refresh_widget_data(self.state_manager.get_current_widgets()):
            self.hub.broadcast_state()
