from typing import List

from .base import Gesture
from .click import ClickGesture
from .pinch import PinchGesture
from .scroll import ScrollGesture
from .swipe import SwipeGesture
from .two_fingers_swipe import TwoFingersSwipeGesture
from .zoom import ZoomGesture


def default_gesture_set() -> List[Gesture]:
    return [
        PinchGesture(),
        ClickGesture(),
        ScrollGesture(),
        ZoomGesture(),
        SwipeGesture(),
        TwoFingersSwipeGesture(),
    ]
