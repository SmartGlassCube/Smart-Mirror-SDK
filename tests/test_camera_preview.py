import base64

import cv2
import numpy as np
from hands import hands, make_hand

from smartmirror.server.camera_preview import CameraPreview, downscale, to_data_url
from smartmirror.vision import GestureDetector, PinchGesture

PREFIX = "data:image/jpeg;base64,"


def decode(url):
    assert url.startswith(PREFIX)
    return cv2.imdecode(np.frombuffer(base64.b64decode(url[len(PREFIX):]), np.uint8), cv2.IMREAD_COLOR)


def test_downscaled_jpeg_data_url():
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    assert decode(to_data_url(downscale(frame, 240))).shape[:2] == (180, 240)


def test_preview_draws_hands_lists_recent_gestures_and_is_throttled():
    detector = GestureDetector(gestures=[PinchGesture()])
    preview = CameraPreview(fps=10, width=240)
    black = np.zeros((480, 640, 3), dtype=np.uint8)

    times = [0.0, 0.03, 0.06, 0.12]
    messages = [
        preview.message(black, detector.process_hands(hands(right=make_hand(0.5 + t, 0.5, pinch=True)), timestamp=t), now=t)
        for t in times
    ]

    assert messages[1:3] == [None, None]  # throttled to 10 fps
    first, last = messages[0], messages[3]
    assert first["type"] == "CAMERA_FRAME"
    assert decode(first["image"]).max() > 100  # hand box/pointer drawn on the black frame
    # pinch_move fired every frame but shows up once
    assert last["events"] == [{"name": "pinch_start", "hand": "right"}, {"name": "pinch_move", "hand": "right"}]
