import json

import websockets


class ClientHub:
    """Tracks connected frontend clients and pushes the mirror state to them.

    Protocol (server -> client): `{"type": "INIT" | "STATE_UPDATE", "state": StateManager.get_state_snapshot()}`.
    Client messages are only logged for now.
    """

    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.clients = set()

    def state_message(self, message_type="STATE_UPDATE"):
        return json.dumps({"type": message_type, "state": self.state_manager.get_state_snapshot()})

    def broadcast_state(self):
        if self.clients:
            websockets.broadcast(self.clients, self.state_message())

    async def handle_client(self, websocket):
        self.clients.add(websocket)
        client_id = id(websocket)
        print(f"[WS] Client {client_id} connected. Total: {len(self.clients)}")

        try:
            await websocket.send(self.state_message("INIT"))
            async for message in websocket:
                print(f"[WS] Received from {client_id}: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"[WS] Client {client_id} disconnected. Total: {len(self.clients)}")
