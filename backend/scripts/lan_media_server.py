#!/usr/bin/env python
"""Serve this machine's webcam and microphone to a mirror over the LAN.

For a mirror (e.g. a Raspberry Pi) with no camera or microphone of its own:
run this on a machine that has them, on the same network, and point the
mirror's .env at it:

    # here (the machine with the webcam + mic):
    uv run python scripts/lan_media_server.py --allow <mirror-ip>

    # the mirror's .env:
    SMARTMIRROR_CAMERA=http://<this-machine-ip>:8081/camera
    SMARTMIRROR_MIC=http://<this-machine-ip>:8081/mic

/camera is an MJPEG stream (multipart/x-mixed-replace), which the mirror's
cv2.VideoCapture(url) reads; /mic is raw mono int16 little-endian PCM at
?rate= (default 16000), which smartmirror.hal.HAL reads for an http://
input_device. The mirror flips and processes frames itself, so they're sent
as the camera captures them.

Only the --allow'ed addresses (plus this machine) may connect; anyone else
gets a 403. This is a live camera and microphone -- never open it to a
whole network.

Needs the assistant extra (sounddevice) on this machine: uv sync --extra assistant.
"""
import argparse
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2

from smartmirror.hal import HAL
from smartmirror.hal.hal import DEFAULT_SAMPLERATE

BOUNDARY = "frame"
JPEG_QUALITY = 80


class CameraFeed:
    """Captures from one camera in a background thread; every /camera client gets the latest JPEG."""

    def __init__(self, camera, width, height):
        self.capture = cv2.VideoCapture(camera)
        if not self.capture.isOpened():
            raise SystemExit(f"lan_media_server: could not open camera {camera}")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._condition = threading.Condition()
        self._jpeg = None
        self._frame_id = 0
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            ok, frame = self.capture.read()
            if not ok:
                continue
            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                with self._condition:
                    self._jpeg = jpeg.tobytes()
                    self._frame_id += 1
                    self._condition.notify_all()

    def next_frame(self, after_id):
        """Block until a frame newer than `after_id`; returns (frame_id, jpeg_bytes)."""
        with self._condition:
            self._condition.wait_for(lambda: self._frame_id > after_id)
            return self._frame_id, self._jpeg


def make_handler(camera_feed, mic_device, allowed):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.client_address[0] not in allowed:
                self.send_error(403, "not in --allow")
                return
            url = urlparse(self.path)
            if url.path == "/camera":
                self._stream_camera()
            elif url.path == "/mic":
                rate = int(parse_qs(url.query).get("rate", [DEFAULT_SAMPLERATE])[0])
                self._stream_mic(rate)
            else:
                self.send_error(404, "use /camera or /mic")

        def _stream_camera(self):
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            frame_id = 0
            try:
                while True:
                    frame_id, jpeg = camera_feed.next_frame(frame_id)
                    self.wfile.write(
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode()
                    )
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _stream_mic(self, rate):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            # HAL does the capture (and resampling, if the mic can't do `rate` natively).
            hal = HAL(samplerate=rate, input_device=mic_device)
            try:
                for block in hal.read_audio():
                    self.wfile.write(block.astype("<i2").tobytes())
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                hal.close()

        def log_message(self, format, *args):
            print(f"[{self.client_address[0]}] {format % args}")

    return Handler


def lan_ip(towards):
    """This machine's address on the interface that reaches `towards` (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect((towards, 9))
            return probe.getsockname()[0]
        except OSError:
            return "<this-machine-ip>"


def main():
    sys.stdout.reconfigure(line_buffering=True)  # show requests live even when piped to a log
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--allow", action="append", required=True, metavar="IP",
                        help="mirror address allowed to connect (repeatable)")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--camera", type=int, default=0, help="local camera index (default 0)")
    parser.add_argument("--mic", default=None, help="sounddevice input device name/index (default: system default)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    mic = int(args.mic) if args.mic is not None and args.mic.isdigit() else args.mic
    allowed = {"127.0.0.1", "::1", *args.allow}
    camera_feed = CameraFeed(args.camera, args.width, args.height)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(camera_feed, mic, allowed))
    server.daemon_threads = True

    host = lan_ip(args.allow[0])
    print(f"lan_media_server: serving camera {args.camera} + mic to {', '.join(args.allow)}")
    print("Put this in the mirror's .env:")
    print(f"  SMARTMIRROR_CAMERA=http://{host}:{args.port}/camera")
    print(f"  SMARTMIRROR_MIC=http://{host}:{args.port}/mic")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
