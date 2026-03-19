from enum import Enum
from dataclasses import dataclass
from typing import Optional


class GestureType(Enum):
    PINCH_START = "pinch_start"
    PINCH_END = "pinch_end"

    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"

    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"

    SCROLL_START = "scroll_start"
    SCROLL_END = "scroll_end"

    ZOOM_START_PINKY_UP = "zoom_start_pinky_up"
    ZOOM_END_PINKY_UP = "zoom_end_pinky_up"
    ZOOM_START_NO_PINKY = "zoom_start_no_pinky"
    ZOOM_END_NO_PINKY = "zoom_end_no_pinky"


@dataclass
class GestureEvent:
    type: GestureType
    hand: Optional[str] = None