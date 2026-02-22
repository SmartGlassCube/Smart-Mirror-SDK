from collections.abc import Set

from .hal import HAL
from .cv import GestureDetector
from .config import StateManager

import os
import urllib.request
import json
import websockets

class SmartMirrorServer:

    def __init__(self,
                  graph,
                  hardware = HAL.HAL(),
                  assistant = None,
                  with_camera = True,
                  with_microphone = False,
                  state_manager = StateManager.StateManager(),
                  gesture_detector = GestureDetector.GestureDetector(),
                  edit_gesture = None,
                  ws_port = 8080):
        
        self.hardware = hardware
        self.state_manager = state_manager
        self.gesture_detector = gesture_detector
        self.ws_port = ws_port
        self.graph = graph
        self.assistant = assistant

        self.edit_gesture = edit_gesture

        self.model_path = self._ensure_model()

        self.clients = set()

        self.running = False
        self.show_debug_window = True

        self.last_hands_update = 0
        self.hands_update_interval = 0.05 

    # can be replaced
    def _ensure_model(self) -> str:
        """Download and return path to hand landmarker model."""
        
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
        return model_path
    
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
                # "state": self.state_manager.get_state_snapshot()
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
                
        # finally:
        #     cap.release()
        #     cv2.destroyAllWindows()
        #     print("[Camera] Stopped capture")
    
    async def run(self):
        """Start the server."""
        print(f"[Server] Starting Smart Mirror Backend")
        print(f"[Server] WebSocket server on ws://localhost:{self.ws_port}")

        self.running = True
        
        async with websockets.serve(self.handle_client, "localhost", self.ws_port):
            await self.camera_loop()