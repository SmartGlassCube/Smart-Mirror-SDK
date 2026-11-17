import json
import logging

import websockets

logger = logging.getLogger(__name__)


class ClientHub:
    """Tracks connected frontend clients and pushes messages to them.

    Protocol (server -> client):
      - `{"type": "WIDGET_TYPES", "widgetTypes": [{"type", "name", "code"}]}`: custom widgets
        (compiled React components, e.g. from a studio project), sent before INIT when there are any
      - `{"type": "INIT" | "STATE_UPDATE", "state": StateManager.get_state_snapshot()}`
      - `{"type": "CAMERA_FRAME", "image": "data:image/jpeg;base64,...", "events": [{"name", "hand"}]}`
        (small annotated webcam preview + latest gestures, see `CameraPreview`)
      - `{"type": "POINTER", "position": {"x", "y"} | None}`: index fingertip for the cursor
        (see `HandPointer`); `None` when the hand is lost
      - `{"type": "ASSISTANT_HEARD", "text": "..."}`: transcript of what the chatbot just heard,
        shown next to the camera preview; `""` when only the wake word was said.
      - `{"type": "ASSISTANT_WAKE"}`: the chatbot heard a question (sent by the server's voice
        loop before the LLM answers); wakes the Abdo avatar. Page changes wake it on their own.
      - `{"type": "ASSISTANT_SAY", "text": "..."}`: chatbot reply; wakes Abdo and types the text
        into his speech bubble, replacing whatever it showed.
    Client messages are only logged for now. Full protocol: docs/protocol.md.
    """

    def __init__(self, state_manager, widget_types=None):
        self.state_manager = state_manager
        self.widget_types = list(widget_types or [])
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
        logger.info("Client %s connected. Total: %d", client_id, len(self.clients))

        try:
            if self.widget_types:
                await websocket.send(json.dumps({"type": "WIDGET_TYPES", "widgetTypes": self.widget_types}))
            await websocket.send(json.dumps(self.state_message("INIT")))
            async for message in websocket:
                logger.info("Received from %s: %s", client_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("Client %s disconnected. Total: %d", client_id, len(self.clients))
