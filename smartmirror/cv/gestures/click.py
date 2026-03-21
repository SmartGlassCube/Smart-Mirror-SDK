from typing import List

from ..gesture_types import GestureEvent, GestureType
from .base import DynamicGesture, GestureContext


class ClickGesture(DynamicGesture):
    name = "click"

    def __init__(self):
        self._prev_index_up = {"left": False, "right": False}
        self._prev_middle_up = {"left": False, "right": False}
        self._prev_hover_posture = {"left": False, "right": False}

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []

        index_up = context.signals["index_up"]
        middle_up = context.signals["middle_up"]
        hover_posture = context.signals["hover_posture"]
        pointer = context.signals["pointer_position"]

        for side in ("left", "right"):
            if self._prev_hover_posture[side]:
                if self._prev_index_up[side] and not index_up[side] and middle_up[side]:
                    events.append(
                        GestureEvent(
                            type=GestureType.LEFT_CLICK,
                            hand=side,
                            location=pointer[side],
                        )
                    )
                elif self._prev_middle_up[side] and not middle_up[side] and index_up[side]:
                    events.append(
                        GestureEvent(
                            type=GestureType.RIGHT_CLICK,
                            hand=side,
                            location=pointer[side],
                        )
                    )

            self._prev_index_up[side] = index_up[side]
            self._prev_middle_up[side] = middle_up[side]
            self._prev_hover_posture[side] = hover_posture[side]

        return events
