"""
class LandmarkDetector:
    def __init__(self):
        # init mediapipe here
        pass

    def extract_hands(self, frame) -> list[HandData]:
        # detect hands
        # convert landmarks
        # return HandData list
        pass
"""

from pathlib import Path
from typing import Dict, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .hand_data import HandData, Landmark, Point2D, BBox


class LandmarkDetector:
    """
    Responsible only for:
    - running MediaPipe Hand Landmarker
    - converting raw results into our HandData structure
    - returning a stable left/right mapping
    """

    RAISED_Y_THRESHOLD = 0.5

    def __init__(
        self,
        model_path: Optional[str] = None,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        if model_path is None:
            model_path_obj = Path(__file__).resolve().parent / "hand_landmarker.task"
        else:
            model_path_obj = Path(model_path)

        if not model_path_obj.exists():
            print(f"[CV] Downloading MediaPipe hand landmarker model to {model_path_obj}...")
            import urllib.request
            model_path_obj.parent.mkdir(parents=True, exist_ok=True)
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, str(model_path_obj))
            print("[CV] Model downloaded successfully.")

        model_path = str(model_path_obj)

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self._timestamp_ms = 0

    def extract_hands(self, frame) -> Dict[str, HandData]:
        """
        Returns:
            {
                "left": HandData(...),
                "right": HandData(...),
            }

        Missing hands are represented by empty HandData objects.
        """
        hands: Dict[str, HandData] = {
            "left": self._empty_hand(),
            "right": self._empty_hand(),
        }

        if frame is None:
            return hands

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        self._timestamp_ms += 33  # simple ~30 FPS step for now
        result = self.landmarker.detect_for_video(mp_image, self._timestamp_ms)

        if not result.hand_landmarks or not result.handedness:
            return hands

        for hand_landmarks, handedness_list in zip(
            result.hand_landmarks, result.handedness
        ):
            if not handedness_list:
                continue

            label = handedness_list[0].category_name.lower()  # "left" or "right"
            if label not in hands:
                continue

            hands[label] = self._build_hand_data(hand_landmarks)

        return hands

    def _build_hand_data(self, hand_landmarks) -> HandData:
        landmarks = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]

        x_values = [lm[0] for lm in landmarks]
        y_values = [lm[1] for lm in landmarks]

        bbox: BBox = (
            min(x_values),
            min(y_values),
            max(x_values),
            max(y_values),
        )

        # Use landmark 9 (middle finger MCP area) as a simple palm-center proxy
        # later we may use barycenter approach as better geometrically true
        palm_center: Point2D = (landmarks[9][0], landmarks[9][1])

        # Wrist is landmark 0
        wrist_y = landmarks[0][1]
        is_raised = wrist_y < self.RAISED_Y_THRESHOLD

        return HandData(
            is_raised=is_raised,
            landmarks=landmarks,
            palm_center=palm_center,
            bbox=bbox,
        )

    def _empty_hand(self) -> HandData:
        return HandData(
            is_raised=False,
            landmarks=None,
            palm_center=None,
            bbox=None,
        )
