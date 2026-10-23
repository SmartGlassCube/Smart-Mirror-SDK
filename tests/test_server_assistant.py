import asyncio

from smartmirror.hal import HAL
from smartmirror.server import SmartMirrorServer


class FakeAssistant:
    """Stands in for Assistant: one voice turn through the hooks, then waits for the stop event."""

    stt = object()

    def __init__(self):
        self.hal = HAL()
        self.listen_kwargs = None

    async def listen_loop(self, hal=None, on_result=None, on_question=None, on_answer=None, stop_event=None):
        self.listen_kwargs = {"hal": hal, "stop_event": stop_event}
        on_question("what's next?")
        on_answer("The workshop, at 14:00.")
        while not stop_event.is_set():
            await asyncio.sleep(0.01)


def test_server_runs_the_assistant_and_drives_abdo(monkeypatch):
    assistant = FakeAssistant()
    server = SmartMirrorServer(graph={"nodes": [{"id": "home", "widgets": []}], "edges": []},
                               with_camera=False, with_frontend=False, ws_port=0, assistant=assistant)
    sent = []
    monkeypatch.setattr(server.hub, "broadcast", sent.append)

    async def main_loop():
        await asyncio.sleep(0.05)
        server.stop()

    monkeypatch.setattr(server, "_main_loop", main_loop)
    asyncio.run(asyncio.wait_for(server.run(), timeout=5))  # the assistant loop must stop with the server

    assert sent == [
        {"type": "ASSISTANT_HEARD", "text": "what's next?"},
        {"type": "ASSISTANT_WAKE"},
        {"type": "ASSISTANT_SAY", "text": "The workshop, at 14:00."},
    ]
    assert assistant.listen_kwargs["hal"] is assistant.hal  # one HAL shared, the assistant's own
    assert server.hardware._closed.is_set()  # mic stream ended so a blocked voice turn can return


def test_server_without_a_voice_assistant_does_not_listen(monkeypatch):
    assistant = FakeAssistant()
    assistant.stt = None
    server = SmartMirrorServer(with_camera=False, with_frontend=False, ws_port=0, assistant=assistant)

    async def main_loop():
        server.stop()

    monkeypatch.setattr(server, "_main_loop", main_loop)
    asyncio.run(asyncio.wait_for(server.run(), timeout=5))

    assert assistant.listen_kwargs is None
