import asyncio
import json
import urllib.error
import urllib.request

import websockets

from glasscube.server import SmartMirrorServer


def _ui(tmp_path):
    ui = tmp_path / "ui"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text("<!doctype html><div id=root></div>")
    (ui / "assets" / "index-abc.js").write_text("console.log(1)")
    (ui / "assets" / "5 1-abc.png").write_bytes(b"png-bytes")
    (tmp_path / "secret.txt").write_text("outside the UI folder")
    return ui


def test_server_serves_the_bundled_ui_next_to_the_websocket(tmp_path):
    server = SmartMirrorServer(with_camera=False, graph={"nodes": [{"id": "home", "widgets": []}], "edges": []})
    server.ui_dir = _ui(tmp_path)

    def get(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.headers.get("Cache-Control"), resp.read()
        except urllib.error.HTTPError as error:
            return error.code, None, None, b""

    async def main():
        nonlocal port
        async with websockets.serve(server.hub.handle_client, "127.0.0.1", 0,
                                    process_request=server._process_http_request) as ws_server:
            port = ws_server.sockets[0].getsockname()[1]
            results = [await asyncio.to_thread(get, path) for path in
                       ("/", "/assets/index-abc.js?v=1", "/nope.js", "/../secret.txt", "/assets/../../secret.txt",
                         "/assets/5%201-abc.png", "/%2e%2e/secret.txt")]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:  # "/" still upgrades
                init = json.loads(await ws.recv())
            return results, init

    port = None
    (index, script, missing, escape, escape_nested, spaced, escape_encoded), init = asyncio.run(main())

    assert index[0] == 200 and index[1].startswith("text/html") and index[2] == "no-cache"
    assert script[:3] == (200, "text/javascript", "max-age=31536000, immutable")
    assert spaced[0] == 200 and spaced[3] == b"png-bytes"  # "5 1-abc.png", requested percent-encoded
    assert missing[0] == escape[0] == escape_nested[0] == escape_encoded[0] == 404
    assert init["type"] == "INIT" and init["state"]["nodeId"] == "home"


def test_server_without_a_bundled_ui_leaves_plain_requests_to_the_websocket(tmp_path):
    server = SmartMirrorServer(with_camera=False, serve_ui=False)
    assert server.ui_dir is None
