from typing import Dict, List, Optional, Tuple

from ..gesture_types import GestureEvent, GestureType
from .base import DynamicGesture, GestureContext


class PinchGesture(DynamicGesture):
    name = "pinch"

    def __init__(self):
        self._pinch_state = {"left": False, "right": False}
        self._prev_pointer: Dict[str, Optional[Tuple[float, float]]] = {
            "left": None,
            "right": None,
        }

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []
        pinching = context.signals["pinching"]
        pointer = context.signals["pointer_position"]

        for side in ("left", "right"):
            current_pointer = pointer[side]

            if pinching[side] and not self._pinch_state[side]:
                events.append(
                    GestureEvent(
                        type=GestureType.PINCH_START,
                        hand=side,
                        location=current_pointer,
                    )
                )
            elif pinching[side] and self._pinch_state[side]:
                prev_pointer = self._prev_pointer[side]
                if current_pointer is not None and prev_pointer is not None:
                    dx = current_pointer[0] - prev_pointer[0]
                    dy = current_pointer[1] - prev_pointer[1]
                    events.append(
                        GestureEvent(
                            type=GestureType.PINCH_MOVE,
                            hand=side,
                            location=current_pointer,
                            data={"dx": dx, "dy": dy},
                        )
                    )
            elif (not pinching[side]) and self._pinch_state[side]:
                events.append(
                    GestureEvent(
                        type=GestureType.PINCH_END,
                        hand=side,
                        location=current_pointer,
                    )
                )

            self._pinch_state[side] = pinching[side]
            self._prev_pointer[side] = current_pointer

        return events