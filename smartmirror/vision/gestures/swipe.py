from typing import Optional

from ..gesture_types import GestureType
from ..hand_data import Point2D
from .base import GestureContext, PostureSwipeGesture


class SwipeGesture(PostureSwipeGesture):
    """One open hand whose palm moves quickly and consistently in one direction."""

    name = "swipe"
    directions = {
        "left": GestureType.SWIPE_LEFT,
        "right": GestureType.SWIPE_RIGHT,
        "up": GestureType.SWIPE_UP,
        "down": GestureType.SWIPE_DOWN,
    }

    def is_ready(self, context: GestureContext, side: str) -> bool:
        return context.signals["open_hand"][side]

    def tracked_point(self, context: GestureContext, side: str) -> Optional[Point2D]:
        return context.hands[side].palm_center
