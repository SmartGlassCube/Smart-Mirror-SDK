from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

from .hand_data import Point2D


class GestureType(str, Enum):
    """Event names emitted by the built-in gestures.

    Custom gestures don't need to extend this enum: `GestureEvent.type` also
    accepts a plain string such as "thumbs_up".
    """

    PINCH_START = "pinch_start"
    PINCH_MOVE = "pinch_move"
    PINCH_END = "pinch_end"

    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"

    TWO_FINGERS_SWIPE_LEFT = "two_fingers_swipe_left"
    TWO_FINGERS_SWIPE_RIGHT = "two_fingers_swipe_right"
    TWO_FINGERS_SWIPE_UP = "two_fingers_swipe_up"
    TWO_FINGERS_SWIPE_DOWN = "two_fingers_swipe_down"

    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"

    SCROLL_START = "scroll_start"
    SCROLL_UPDATE = "scroll_update"
    SCROLL_END = "scroll_end"

    ZOOM_START_PINKY_UP = "zoom_start_pinky_up"
    ZOOM_UPDATE_PINKY_UP = "zoom_update_pinky_up"
    ZOOM_END_PINKY_UP = "zoom_end_pinky_up"
    ZOOM_START_NO_PINKY = "zoom_start_no_pinky"
    ZOOM_UPDATE_NO_PINKY = "zoom_update_no_pinky"
    ZOOM_END_NO_PINKY = "zoom_end_no_pinky"


@dataclass
class GestureEvent:
    type: Union[GestureType, str]
    hand: Optional[str] = None
    location: Optional[Point2D] = None
    data: Optional[Dict[str, Any]] = None

    @property
    def name(self) -> str:
        """Event name used for bindings and graph edges, e.g. "swipe_left"."""
        return self.type.value if isinstance(self.type, Enum) else str(self.type)
