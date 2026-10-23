import asyncio
import urllib.error
import urllib.request
from pathlib import Path

import websockets

from smartmirror.server import SmartMirrorServer


class FakeContentSync:
    """Just what the server needs from ContentSync to serve images."""

    def __init__(self, images_dir: Path):
        self.images_dir = images_dir
        self.image_base_url = None


def _server(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "abc123.png").write_bytes(b"\x89PNG fake")
    (images / ".abc123.tmp").write_bytes(b"partial")
    content_sync = FakeContentSync(images)
    server = SmartMirrorServer(with_camera=False, with_frontend=False, ws_port=8765, content_sync=content_sync)
    return server, content_sync


def test_server_tells_content_sync_where_images_are_served(tmp_path):
    _server_, content_sync = _server(tmp_path)
    assert content_sync.image_base_url == "http://localhost:8765/content-images"


def test_server_serves_event_images_next_to_the_websocket(tmp_path):
    server, _content_sync = _server(tmp_path)

    def get(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as error:
            return error.code, None, b""

    async def main():
        nonlocal port
        async with websockets.serve(server.hub.handle_client, "127.0.0.1", 0,
                                    process_request=server._serve_content_image) as ws_server:
            port = ws_server.sockets[0].getsockname()[1]
            image = await asyncio.to_thread(get, "/content-images/abc123.png")
            missing = await asyncio.to_thread(get, "/content-images/nope.png")
            hidden = await asyncio.to_thread(get, "/content-images/.abc123.tmp")
            escape = await asyncio.to_thread(get, "/content-images/../app.py")
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:  # the WebSocket still works
                await ws.ping()
            return image, missing, hidden, escape

    port = None
    image, missing, hidden, escape = asyncio.run(main())

    assert image == (200, "image/png", b"\x89PNG fake")
    assert missing[0] == hidden[0] == escape[0] == 404
