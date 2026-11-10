import base64
from typing import Optional

import cv2

from ..vision import DebugOverlay


def downscale(frame, width: int):
    height = max(1, round(frame.shape[0] * width / frame.shape[1]))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def to_data_url(image, quality: int = 60) -> str:
    """JPEG-encode a BGR image as a data URL the frontend can show in an <img>."""
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Could not JPEG-encode the camera preview")
    return "data:image/jpeg;base64," + base64.b64encode(jpeg.tobytes()).decode("ascii")


class CameraPreview:
    """Builds the frontend's corner webcam view: a small annotated frame plus the latest gesture names."""

    def __init__(self, fps: float = 10, width: int = 240, quality: int = 60, max_events: int = 3):
        self.interval = 1.0 / fps
        self.width = width
        self.quality = quality
        self.max_events = max_events
        self.overlay = DebugOverlay()
        self._last_sent = float("-inf")

    def message(self, frame, detection: dict, now: float) -> Optional[dict]:
        """Call for every processed frame; returns a `CAMERA_FRAME` message when one is due."""
        self.overlay.remember(detection["signals"], detection["events"], now)
        if now - self._last_sent < self.interval:
            return None
        self._last_sent = now

        image = downscale(frame, self.width)
        self.overlay.draw(image, detection["hands"], detection["signals"], now, labels=False)
        return {
            "type": "CAMERA_FRAME",
            "image": to_data_url(image, self.quality),
            "events": self._recent_events(now),
        }

    def _recent_events(self, now: float):
        events = []
        for event in self.overlay.recent_events(now, window=1.5):
            entry = {"name": event.name, "hand": event.hand}
            if not events or events[-1] != entry:  # collapse repeats like pinch_move
                events.append(entry)
        return events[-self.max_events:]
