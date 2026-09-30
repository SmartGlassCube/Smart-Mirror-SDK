from typing import Optional

from ..gesture_types import GestureType
from ..hand_data import Point2D
from .base import GestureContext, PostureSwipeGesture


class TwoFingersSwipeGesture(PostureSwipeGesture):
    """One hand with only index + middle fingers up, moving quickly in one direction."""

    name = "two_fingers_swipe"
    directions = {
        "left": GestureType.TWO_FINGERS_SWIPE_LEFT,
        "right": GestureType.TWO_FINGERS_SWIPE_RIGHT,
        "up": GestureType.TWO_FINGERS_SWIPE_UP,
        "down": GestureType.TWO_FINGERS_SWIPE_DOWN,
    }

    def __init__(self, threshold_x=0.10, threshold_y=0.10, time_window=0.40, cooldown=0.70, **kwargs):
        super().__init__(
            threshold_x=threshold_x,
            threshold_y=threshold_y,
            time_window=time_window,
            cooldown=cooldown,
            **kwargs,
        )

    def is_ready(self, context: GestureContext, side: str) -> bool:
        signals = context.signals
        return (
            signals["index_up"][side]
            and signals["middle_up"][side]
            and not signals["ring_up"][side]
            and not signals["pinky_up"][side]
            and not signals["pinching"][side]
        )

    def tracked_point(self, context: GestureContext, side: str) -> Optional[Point2D]:
        return context.signals["pointer_position"][side]
