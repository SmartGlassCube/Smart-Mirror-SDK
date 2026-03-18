from enum import Enum
from dataclasses import dataclass
from typing import Optional


class GestureType(Enum):
    PINCH_START = "pinch_start"
    PINCH_END = "pinch_end"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"


@dataclass
class GestureEvent:
    type: GestureType
    hand: Optional[str] = None  # "left", "right", or None if not hand-specific