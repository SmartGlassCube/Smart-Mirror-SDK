from .hal import HAL
from .cv import GestureDetector
from .config import StateManager

import asyncio
import inspect
import logging
import cv2
from pathlib import Path
import os
import urllib.request
import json
import shutil
import time
import websockets

logger = logging.getLogger(__name__)

class SmartMirrorServer:

    def __init__(self,
                  graph,
                  hardware = None,
                  assistant = None,
                  assistant_widget = None,
                  with_camera = True,
                  with_microphone = False,
                  state_manager = None,
                  gesture_detector = None,
                  edit_gesture = None,
                  ws_port = 8080,
                  with_ui = True,
                  ui_dir = None,
                  ui_host = "localhost",
                  ui_port = 5173,
                  camera_id = 0):
        
        self.hardware = hardware or HAL()
        self.state_manager = state_manager or StateManager(graph=graph)
        self.gesture_detector = gesture_detector or GestureDetector()
        self.ws_port = ws_port
        self.graph = graph
        self.assistant = assistant
        self.assistant_widget = assistant_widget
        self.with_camera = with_camera
        self.with_microphone = with_microphone
        self.with_ui = with_ui
        self.ui_host = ui_host
        self.ui_port = ui_port
        self.ui_dir = Path(ui_dir) if ui_dir else self._get_default_ui_dir()
        self.ui_process = None
        self.camera_id = camera_id

        self.edit_gesture = edit_gesture

        self.state_manager.set_graph(self.graph)

        self.model_path = self._ensure_model()

        self.clients = set()

        self.running = False
        self.show_debug_window = True

        self.last_hands_update = 0
        self.hands_update_interval = 0.05 
        self.widget_update_tick = 0.5

    # can be replaced
    def _ensure_model(self) -> str:
        """Download and return path to hand landmarker model."""
        model_path = Path(__file__).resolve().parent / "cv" / "hand_landmarker.task"
        model_path.parent.mkdir(parents=True, exist_ok=True)

        if not model_path.exists():
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, str(model_path))
        return str(model_path)

    def _get_default_ui_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "ui"

    async def _ensure_ui_dependencies(self):
        if not self.ui_dir.exists():
            print(f"[UI] Skipping launch: UI directory not found at {self.ui_dir}")
            return False

        # TODO: install npm if not found
        if shutil.which("npm") is None:
            print("[UI] Skipping launch: npm is not installed or not in PATH")
            return False

        node_modules = self.ui_dir / "node_modules"
        if node_modules.exists():
            return True

        print("[UI] Installing UI dependencies (npm install)...")
        install_process = await asyncio.create_subprocess_exec(
            "npm",
            "install",
            cwd=str(self.ui_dir),
        )
        return_code = await install_process.wait()
        if return_code != 0:
            print(f"[UI] npm install failed with exit code {return_code}")
            return False

        return True

    async def _start_ui(self):
        if not self.with_ui:
            return

        if not await self._ensure_ui_dependencies():
            return

        print(f"[UI] Starting UI on http://{self.ui_host}:{self.ui_port}")
        self.ui_process = await asyncio.create_subprocess_exec(
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            self.ui_host,
            "--port",
            str(self.ui_port),
            cwd=str(self.ui_dir),
        )

    async def _stop_ui(self):
        if self.ui_process is None:
            return

        self.ui_process.terminate()
        await self.ui_process.wait()
        self.ui_process = None
    
    async def broadcast(self, message: dict):
        """Send message to all connected WebSocket clients."""

        if not self.clients:
            return
        
        json_message = json.dumps(message)
        print(f"[WS] Broadcasting: {json_message}")
        
        clients_copy = self.clients.copy()
        disconnected = set()
        
        for client in clients_copy:
            try:
                await client.send(json_message)
            except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
                disconnected.add(client)
            except Exception as e:
                print(f"[WS] Error sending to client {id(client)}: {e}")
                disconnected.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected

    async def handle_client(self, websocket):
        """Handle a new WebSocket client connection."""
        self.clients.add(websocket)
        client_id = id(websocket)
        print(f"[WS] Client {client_id} connected. Total: {len(self.clients)}")
        
        try:
            # Send initial state
            await websocket.send(json.dumps({
                "type": "INIT",
                "state": self.state_manager.get_state_snapshot()
            }))
            
            # Keep connection open, handle any incoming messages
            async for message in websocket:
                print(f"[WS] Received from {client_id}: {message}")
                
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
            # Normal disconnect
            pass
        except Exception as e:
            print(f"[WS] Error with client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            print(f"[WS] Client {client_id} disconnected. Total: {len(self.clients)}")

    async def _run_data_provider(self, widget):
        provider = getattr(widget, "data_provider", None)
        if provider is None:
            return None

        try:
            value = provider(widget)
        except TypeError:
            value = provider()

        if inspect.isawaitable(value):
            value = await value

        return value

    async def _refresh_widget_data(self):
        widgets = self.state_manager.get_current_widgets()
        if not widgets:
            return

        now = time.time()
        changed = False

        for widget in widgets:
            provider = getattr(widget, "data_provider", None)
            if provider is None:
                continue

            interval = getattr(widget, "refresh_interval", 60) or 60
            last_update = getattr(widget, "_last_data_update", 0.0)

            if now - last_update < interval:
                continue

            try:
                new_data = await self._run_data_provider(widget)
            except Exception as error:
                print(f"[WidgetData] Failed to refresh {getattr(widget, 'type', 'unknown')} widget: {error}")
                widget._last_data_update = now
                continue

            previous_data = getattr(widget, "data", None)
            widget.data = new_data
            widget._last_data_update = now

            if previous_data != new_data:
                changed = True

        if changed:
            await self.broadcast({
                "type": "STATE_UPDATE",
                "state": self.state_manager.get_state_snapshot(),
            })

    async def camera_loop(self):
        if not self.with_camera:
            while self.running:
                await self._refresh_widget_data()
                await asyncio.sleep(self.widget_update_tick)
            return

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f"[Camera] Could not open camera {self.camera_id}; running in data-only mode")
            while self.running:
                await self._refresh_widget_data()
                await asyncio.sleep(self.widget_update_tick)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        last_widget_refresh = 0.0

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.02)
                    continue

                try:
                    frame = cv2.flip(frame, 1)
                    detector_output = self.gesture_detector.process_frame(frame)

                    if self.state_manager.handle_gesture_events(
                        events=detector_output.get("events", []),
                        signals=detector_output.get("signals", {}),
                    ):
                        await self.broadcast(
                            {
                                "type": "STATE_UPDATE",
                                "state": self.state_manager.get_state_snapshot(),
                            }
                        )

                    now = time.time()
                    if now - last_widget_refresh >= self.widget_update_tick:
                        await self._refresh_widget_data()
                        last_widget_refresh = now

                    if self.show_debug_window and self.gesture_detector.debug:
                        cv2.imshow("Smart Mirror - Debug", frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord("q"):
                            self.running = False
                except Exception:
                    # One bad frame (a gesture-detector hiccup, a broadcast
                    # error, ...) must not take gesture nav down for the
                    # whole session -- log it and keep processing frames.
                    logger.exception("camera_loop: error processing a frame -- skipping it")

                await asyncio.sleep(0.01)
        finally:
            cap.release()
            if self.gesture_detector.debug:
                cv2.destroyAllWindows()
    
    async def _handle_assistant_result(self, result):
        """Report one voice exchange {"transcript", "answer"} through the existing
        broadcast()/STATE_UPDATE mechanism -- no parallel channel, no protocol
        the UI doesn't already know how to render.

        Updates self.assistant_widget's content (a plain TextWidget, so
        App.tsx renders it with zero frontend changes) and re-broadcasts the
        state snapshot, exactly like a gesture-driven state change does.
        """
        transcript = result.get("transcript") or ""
        answer = result.get("answer") or ""

        if self.assistant_widget is not None:
            self.assistant_widget.content = f"You: {transcript}\nAssistant: {answer}"

        await self.broadcast({
            "type": "STATE_UPDATE",
            "state": self.state_manager.get_state_snapshot(),
        })

    async def assistant_loop(self):
        """Run the assistant's wake-word -> STT -> chat() loop, gated by with_microphone.

        Scheduled alongside camera_loop via asyncio.gather in run() so voice
        and gesture input are handled concurrently, not one blocking the
        other. Mic/speaker I/O goes through self.hardware (HAL), the same
        instance camera_loop's sibling components would use, so a future
        Pi-specific HAL swap only has to happen in one place.
        """
        if not self.with_microphone or self.assistant is None:
            return

        await self.assistant.listen_loop(hal=self.hardware, on_result=self._handle_assistant_result)

    async def run(self):
        """Start the server."""
        print(f"[Server] Starting Smart Mirror Backend")
        print(f"[Server] WebSocket server on ws://localhost:{self.ws_port}")

        self.running = True

        try:
            async with websockets.serve(self.handle_client, "localhost", self.ws_port):
                await self._start_ui()
                # return_exceptions=True: an unhandled failure in one loop
                # (e.g. assistant_loop) must not cancel the other (e.g.
                # camera_loop) -- gesture nav should keep working even if
                # voice is having a bad day, and vice versa. This only
                # covers ordinary Python exceptions; a segfault in a native
                # library (whisper.cpp/mediapipe/PortAudio) still kills the
                # whole process -- see scripts/voice_pipeline_manual_test.md
                # for why this needs process-level supervision too.
                results = await asyncio.gather(
                    self.camera_loop(), self.assistant_loop(), return_exceptions=True
                )
                for result in results:
                    if isinstance(result, Exception):
                        logger.error("A server loop exited with an unhandled exception", exc_info=result)
        finally:
            await self._stop_ui()