import json

import websockets


class ClientHub:
    """Tracks connected frontend clients and pushes messages to them.

    Protocol (server -> client):
      - `{"type": "INIT" | "STATE_UPDATE", "state": StateManager.get_state_snapshot()}`
      - `{"type": "CAMERA_FRAME", "image": "data:image/jpeg;base64,...", "events": [{"name", "hand"}]}`
        (small annotated webcam preview + latest gestures, see `CameraPreview`)
      - `{"type": "ASSISTANT_WAKE"}`: someone talked to the chatbot; wakes the Abdo avatar
        (`hub.broadcast({"type": "ASSISTANT_WAKE"})`). Page changes wake it on their own.
    Client messages are only logged for now.
    """

    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.clients = set()

    def state_message(self, message_type="STATE_UPDATE"):
        return {"type": message_type, "state": self.state_manager.get_state_snapshot()}

    def broadcast(self, message):
        if self.clients:
            websockets.broadcast(self.clients, json.dumps(message))

    def broadcast_state(self):
        self.broadcast(self.state_message())

    async def handle_client(self, websocket):
        self.clients.add(websocket)
        client_id = id(websocket)
        print(f"[WS] Client {client_id} connected. Total: {len(self.clients)}")

        try:
            await websocket.send(json.dumps(self.state_message("INIT")))
            async for message in websocket:
                print(f"[WS] Received from {client_id}: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[WS] Client {client_id} disconnected. Total: {len(self.clients)}")
