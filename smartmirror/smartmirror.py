from .hal import HAL
from .cv import GestureDetector
from .config import StateManager

import asyncio
import inspect
from pathlib import Path
import os
import urllib.request
import json
import shutil
import time
import websockets

class SmartMirrorServer:

    def __init__(self,
                  graph,
                  hardware = None,
                  assistant = None,
                  with_camera = True,
                  with_microphone = False,
                  state_manager = None,
                  gesture_detector = None,
                  edit_gesture = None,
                  ws_port = 8080,
                  with_ui = True,
                  ui_dir = None,
                  ui_host = "localhost",
                  ui_port = 5173):
        
        self.hardware = hardware or HAL.HAL()
        self.state_manager = state_manager or StateManager.StateManager()
        self.gesture_detector = gesture_detector or GestureDetector()
        self.ws_port = ws_port
        self.graph = graph
        self.assistant = assistant
        self.with_camera = with_camera
        self.with_microphone = with_microphone
        self.with_ui = with_ui
        self.ui_host = ui_host
        self.ui_port = ui_port
        self.ui_dir = Path(ui_dir) if ui_dir else self._get_default_ui_dir()
        self.ui_process = None

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
        
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
        return model_path

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
        """Main camera processing loop."""
        # cap = cv2.VideoCapture(self.camera_id)
        
        # if not cap.isOpened():
        #     print(f"[ERROR] Could not open camera {self.camera_id}")
        #     return
        
        # print(f"[Camera] Started capture from camera {self.camera_id}")
        
        # # Set camera properties for better performance
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # cap.set(cv2.CAP_PROP_FPS, 30)
        
        # self.running = True
        # frame_count = 0
        
        # try:
        #     while self.running:
        #         ret, frame = cap.read()
        #         if not ret:
        #             print("[Camera] Failed to read frame")
        #             await asyncio.sleep(0.1)
        #             continue
                
        #         # Mirror the frame for more intuitive interaction
        #         frame = cv2.flip(frame, 1)
                
        #         # Process frame and get events
        #         events = self.process_frame(frame)
                
        #         # Broadcast events
        #         for event in events:
        #             await self.broadcast(event)
                
        #         # Show debug window
        #         if self.show_debug_window:
        #             cv2.imshow("Smart Mirror - Debug", frame)
        #             key = cv2.waitKey(1) & 0xFF
        #             if key == ord('q'):
        #                 self.running = False
        #             elif key == ord('d'):
        #                 # Toggle debug window
        #                 self.show_debug_window = not self.show_debug_window
                
        #         frame_count += 1
                
        #         # Small delay to prevent CPU overload
        #         await asyncio.sleep(0.01)
                
        while self.running:
            await self._refresh_widget_data()
            await asyncio.sleep(self.widget_update_tick)
    
    async def run(self):
        """Start the server."""
        print(f"[Server] Starting Smart Mirror Backend")
        print(f"[Server] WebSocket server on ws://localhost:{self.ws_port}")

        self.running = True

        try:
            async with websockets.serve(self.handle_client, "localhost", self.ws_port):
                await self._start_ui()
                await self.camera_loop()
        finally:
            await self._stop_ui()