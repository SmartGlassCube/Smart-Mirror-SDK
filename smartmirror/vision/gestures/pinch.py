from typing import Dict, List, Optional

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import SIDES, Point2D
from .base import Gesture, GestureContext


class PinchGesture(Gesture):
    """Thumb + index pinch. `pinch_move` carries the pointer delta in `data: {dx, dy}`."""

    name = "pinch"

    def __init__(self):
        self._pinching = {side: False for side in SIDES}
        self._prev_pointer: Dict[str, Optional[Point2D]] = {side: None for side in SIDES}

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []
        pinching = context.signals["pinching"]
        pointer = context.signals["pointer_position"]

        for side in SIDES:
            current = pointer[side]
            previous = self._prev_pointer[side]
            was_pinching = self._pinching[side]

            if pinching[side] and not was_pinching:
                events.append(GestureEvent(type=GestureType.PINCH_START, hand=side, location=current))
            elif pinching[side] and current is not None and previous is not None:
                events.append(
                    GestureEvent(
                        type=GestureType.PINCH_MOVE,
                        hand=side,
                        location=current,
                        data={"dx": current[0] - previous[0], "dy": current[1] - previous[1]},
                    )
                )
            elif not pinching[side] and was_pinching:
                events.append(GestureEvent(type=GestureType.PINCH_END, hand=side, location=current))

            self._pinching[side] = pinching[side]
            self._prev_pointer[side] = current

        return events
