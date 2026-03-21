from typing import List

from ..gesture_types import GestureEvent, GestureType
from .base import DynamicGesture, GestureContext


class ZoomGesture(DynamicGesture):
    name = "zoom"

    def __init__(self, start_delta: float = 0.025, end_delta: float = 0.015):
        self.start_delta = start_delta
        self.end_delta = end_delta
        self._zoom_state_pinky_up = {"left": False, "right": False}
        self._zoom_state_no_pinky = {"left": False, "right": False}

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []

        mode_pinky = context.signals["zoom_mode_pinky_up"]
        mode_no_pinky = context.signals["zoom_mode_no_pinky"]
        span_delta = context.signals["thumb_index_distance_delta"]
        pointer = context.signals["pointer_position"]

        for side in ("left", "right"):
            delta = span_delta[side]

            if mode_pinky[side] and delta is not None and abs(delta) >= self.start_delta:
                if not self._zoom_state_pinky_up[side]:
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_START_PINKY_UP,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": delta},
                        )
                    )
                    self._zoom_state_pinky_up[side] = True
                else:
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_UPDATE_PINKY_UP,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": delta},
                        )
                    )
            elif self._zoom_state_pinky_up[side]:
                if (not mode_pinky[side]) or (delta is None) or (abs(delta) <= self.end_delta):
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_END_PINKY_UP,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": 0.0 if delta is None else delta},
                        )
                    )
                    self._zoom_state_pinky_up[side] = False

            if mode_no_pinky[side] and delta is not None and abs(delta) >= self.start_delta:
                if not self._zoom_state_no_pinky[side]:
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_START_NO_PINKY,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": delta},
                        )
                    )
                    self._zoom_state_no_pinky[side] = True
                else:
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_UPDATE_NO_PINKY,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": delta},
                        )
                    )
            elif self._zoom_state_no_pinky[side]:
                if (not mode_no_pinky[side]) or (delta is None) or (abs(delta) <= self.end_delta):
                    events.append(
                        GestureEvent(
                            type=GestureType.ZOOM_END_NO_PINKY,
                            hand=side,
                            location=pointer[side],
                            data={"span_delta": 0.0 if delta is None else delta},
                        )
                    )
                    self._zoom_state_no_pinky[side] = False

        return events
