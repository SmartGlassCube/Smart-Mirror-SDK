from typing import List

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import SIDES
from .base import Gesture, GestureContext


class ClickGesture(Gesture):
    """From the hover posture, fold the index (left click) or the middle finger (right click)."""

    name = "click"

    def __init__(self):
        self._prev_index_up = {side: False for side in SIDES}
        self._prev_middle_up = {side: False for side in SIDES}
        self._prev_hover_posture = {side: False for side in SIDES}

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []
        index_up = context.signals["index_up"]
        middle_up = context.signals["middle_up"]
        pointer = context.signals["pointer_position"]

        for side in SIDES:
            if self._prev_hover_posture[side]:
                click = None
                if self._prev_index_up[side] and not index_up[side] and middle_up[side]:
                    click = GestureType.LEFT_CLICK
                elif self._prev_middle_up[side] and not middle_up[side] and index_up[side]:
                    click = GestureType.RIGHT_CLICK
                if click is not None:
                    events.append(GestureEvent(type=click, hand=side, location=pointer[side]))

            self._prev_index_up[side] = index_up[side]
            self._prev_middle_up[side] = middle_up[side]
            self._prev_hover_posture[side] = context.signals["hover_posture"][side]

        return events
