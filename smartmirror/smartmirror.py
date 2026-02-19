from .hal import HAL
from .cv import GestureDetector
from .config import StateManager

import os
import urllib.request

class SmartMirrorServer:

    def __init__(self, hardware = HAL.HAL(),
                  state_manager = StateManager.StateManager(),
                  gesture_detector = GestureDetector.GestureDetector(),
                  ws_port = 8080):
        
        self.hardware = hardware
        self.state_manager = state_manager
        self.gesture_detector = gesture_detector
        self.ws_port = ws_port

        self.model_path = self._ensure_model()


    def _ensure_model(self) -> str:
        """Download and return path to hand landmarker model."""
        
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, model_path)
        return model_path