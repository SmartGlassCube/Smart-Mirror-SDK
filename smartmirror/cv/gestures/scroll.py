from typing import List

from ..gesture_types import GestureEvent, GestureType
from .base import DynamicGesture, GestureContext


class ScrollGesture(DynamicGesture):
    name = "scroll"

    def __init__(self, start_delta_y: float = 0.05, end_delta_y: float = 0.02):
        self.start_delta_y = start_delta_y
        self.end_delta_y = end_delta_y
        self._scroll_state = {"left": False, "right": False}

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []

        hover_posture = context.signals["hover_posture"]
        vertical_delta = context.signals["vertical_delta"]
        pointer = context.signals["pointer_position"]

        for side in ("left", "right"):
            vy = vertical_delta[side]

            if hover_posture[side] and vy is not None and abs(vy) >= self.start_delta_y:
                if not self._scroll_state[side]:
                    events.append(
                        GestureEvent(
                            type=GestureType.SCROLL_START,
                            hand=side,
                            location=pointer[side],
                            data={"velocity_y": vy},
                        )
                    )
                    self._scroll_state[side] = True
                else:
                    events.append(
                        GestureEvent(
                            type=GestureType.SCROLL_UPDATE,
                            hand=side,
                            location=pointer[side],
                            data={"velocity_y": vy},
                        )
                    )
            elif self._scroll_state[side]:
                if (not hover_posture[side]) or (vy is None) or (abs(vy) <= self.end_delta_y):
                    events.append(
                        GestureEvent(
                            type=GestureType.SCROLL_END,
                            hand=side,
                            location=pointer[side],
                            data={"velocity_y": 0.0 if vy is None else vy},
                        )
                    )
                    self._scroll_state[side] = False

        return events
