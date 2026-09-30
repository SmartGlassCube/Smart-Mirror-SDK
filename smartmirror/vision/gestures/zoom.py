from typing import List

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import SIDES
from .base import ContinuousGesture, GestureContext

# mode signal -> (start, update, end) events
_MODES = {
    "zoom_mode_pinky_up": (
        GestureType.ZOOM_START_PINKY_UP,
        GestureType.ZOOM_UPDATE_PINKY_UP,
        GestureType.ZOOM_END_PINKY_UP,
    ),
    "zoom_mode_no_pinky": (
        GestureType.ZOOM_START_NO_PINKY,
        GestureType.ZOOM_UPDATE_NO_PINKY,
        GestureType.ZOOM_END_NO_PINKY,
    ),
}


class ZoomGesture(ContinuousGesture):
    """One-hand thumb/index span changing, in two modes (pinky up / pinky down). Data: `span_delta`."""

    name = "zoom"

    def __init__(self, start_delta: float = 0.025, end_delta: float = 0.015):
        super().__init__()
        self.start_delta = start_delta
        self.end_delta = end_delta

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []
        span_delta = context.signals["thumb_index_distance_delta"]
        pointer = context.signals["pointer_position"]

        for side in SIDES:
            delta = span_delta[side]
            for mode_signal, mode_events in _MODES.items():
                in_mode = context.signals[mode_signal][side]
                events += self._phase(
                    side=side,
                    triggered=in_mode and delta is not None and abs(delta) >= self.start_delta,
                    ended=not in_mode or delta is None or abs(delta) <= self.end_delta,
                    events=mode_events,
                    location=pointer[side],
                    data={"span_delta": delta},
                    end_data={"span_delta": 0.0 if delta is None else delta},
                    channel=mode_signal,
                )

        return events
