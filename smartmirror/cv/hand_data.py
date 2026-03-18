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
                self.left = positions
            else:
                self.right = positions

    def close(self):
        self._landmarker.close()