from dataclasses import dataclass
from typing import List, Tuple, Optional

Landmark = Tuple[float, float, float] #each landmark is (x,y,z)
Point2D = Tuple[float, float] #(x,y) coordinates of the palm center, can be used for gesture recognition and hand tracking
BBox = Tuple[float, float, float, float] #(x_min, y_min, x_max, y_max) coordinates of the bounding box around the hand, can be used for gesture recognition and hand tracking

@dataclass
class HandData:
    is_raised: bool #raised or not ?
    # all those are optional because no hand => nth else
    landmarks: Optional[List[Landmark]]
    palm_center: Optional[Point2D]
    bbox: Optional[BBox]

#lena tebda 5edmet khammar
      
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import os


class HandsData:
    def __init__(self):
        self.right = [None] * 21
        self.left  = [None] * 21

        # model is in the same folder as this file
        model_path = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._timestamp  = 0

    def update(self, frame):
        self.right = [None] * 21
        self.left  = [None] * 21

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        self._timestamp += 1
        result = self._landmarker.detect_for_video(mp_image, self._timestamp)

        for hand_landmarks, handedness in zip(result.hand_landmarks,
                                              result.handedness):
            label = handedness[0].category_name
            positions = [(lm.x, lm.y, lm.z) for lm in hand_landmarks]

            if label == "Left":
                self.right = positions
            else:
                self.left = positions

    def close(self):
        self._landmarker.close()
