import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from smartmirror.hal import HAL, is_stream_url


def serve_once(body):
    """A one-shot HTTP server that answers every GET with `body`, then closes; returns (url, requested_paths)."""
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/mic", paths


def test_is_stream_url():
    assert is_stream_url("http://10.0.0.2:8081/mic")
    assert not is_stream_url(None)
    assert not is_stream_url(0)
    assert not is_stream_url("pulse")


def test_network_mic_yields_int16_blocks_then_raises_when_the_stream_ends():
    samples = np.arange(2 * 160 + 50, dtype="<i2")  # two full blocks plus a partial one
    url, paths = serve_once(samples.tobytes())
    hal = HAL(blocksize=160, input_device=url)

    blocks = []
    with pytest.raises(ConnectionError):
        blocks.extend(hal.read_audio())  # keeps the blocks yielded before the stream ended

    assert paths == ["/mic?rate=16000"]
    assert [b.dtype for b in blocks] == [np.int16, np.int16]
    np.testing.assert_array_equal(np.concatenate(blocks), samples[:320])
