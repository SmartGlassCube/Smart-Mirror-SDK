from typing import List

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import SIDES
from .base import ContinuousGesture, GestureContext

_EVENTS = (GestureType.SCROLL_START, GestureType.SCROLL_UPDATE, GestureType.SCROLL_END)


class ScrollGesture(ContinuousGesture):
    """Hover posture (index + middle up) moving vertically. Data: `velocity_y`."""

    name = "scroll"

    def __init__(self, start_delta_y: float = 0.05, end_delta_y: float = 0.02):
        super().__init__()
        self.start_delta_y = start_delta_y
        self.end_delta_y = end_delta_y

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []
        hover_posture = context.signals["hover_posture"]
        pointer = context.signals["pointer_position"]

        for side in SIDES:
            vy = context.signals["vertical_delta"][side]
            events += self._phase(
                side=side,
                triggered=hover_posture[side] and vy is not None and abs(vy) >= self.start_delta_y,
                ended=not hover_posture[side] or vy is None or abs(vy) <= self.end_delta_y,
                events=_EVENTS,
                location=pointer[side],
                data={"velocity_y": vy},
                end_data={"velocity_y": 0.0 if vy is None else vy},
            )

        return events
