import urllib.request
from pathlib import Path
from typing import Dict, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .hand_data import MIDDLE_MCP, SIDES, WRIST, BBox, HandData, Point2D

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "hand_landmarker.task"
_OTHER_SIDE = {"left": "right", "right": "left"}


def ensure_model(model_path: Path = DEFAULT_MODEL_PATH) -> Path:
    """Download the MediaPipe hand landmarker model if it isn't there yet."""
    if not model_path.exists():
        print(f"[Vision] Downloading MediaPipe hand landmarker model to {model_path}...")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, str(model_path))
    return model_path


class LandmarkDetector:
    """Runs the MediaPipe Hand Landmarker and returns a stable `{"left": HandData, "right": HandData}`.

    Sides are the user's own hands. The pipeline feeds mirrored (flipped) frames, on which
    MediaPipe reports the opposite hand, so its labels are swapped by default; pass
    `swap_handedness=False` for frames that are not flipped.
    """

    RAISED_Y_THRESHOLD = 0.5

    def __init__(
        self,
        model_path: Optional[str] = None,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        swap_handedness: bool = True,
    ):
        self.swap_handedness = swap_handedness
        model = ensure_model(Path(model_path) if model_path else DEFAULT_MODEL_PATH)
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self._timestamp_ms = 0

    def extract_hands(self, frame) -> Dict[str, HandData]:
        """Missing hands are returned as `HandData.empty()`."""
        hands = {side: HandData.empty() for side in SIDES}
        if frame is None:
            return hands

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        self._timestamp_ms += 33  # ~30 FPS step
        result = self.landmarker.detect_for_video(mp_image, self._timestamp_ms)

        for hand_landmarks, handedness in zip(result.hand_landmarks or [], result.handedness or []):
            if not handedness:
                continue
            label = handedness[0].category_name.lower()
            if self.swap_handedness:
                label = _OTHER_SIDE.get(label, label)
            if label in hands:
                hands[label] = self._build_hand_data(hand_landmarks)

        return hands

    def close(self) -> None:
        self.landmarker.close()

    def _build_hand_data(self, hand_landmarks) -> HandData:
        landmarks = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]
        xs = [lm[0] for lm in landmarks]
        ys = [lm[1] for lm in landmarks]
        bbox: BBox = (min(xs), min(ys), max(xs), max(ys))

        # Middle-finger MCP as a simple palm-center proxy.
        palm_center: Point2D = (landmarks[MIDDLE_MCP][0], landmarks[MIDDLE_MCP][1])

        return HandData(
            is_raised=landmarks[WRIST][1] < self.RAISED_Y_THRESHOLD,
            landmarks=landmarks,
            palm_center=palm_center,
            bbox=bbox,
        )
