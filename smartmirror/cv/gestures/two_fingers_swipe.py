from typing import List, Optional, Tuple

from ..gesture_types import GestureEvent, GestureType
from .base import DynamicGesture, GestureContext


class TwoFingersSwipeGesture(DynamicGesture):
    name = "two_fingers_swipe"

    def __init__(
        self,
        threshold_x: float = 0.10,
        threshold_y: float = 0.10,
        time_window: float = 0.40,
        cooldown: float = 0.70,
        min_samples: int = 4,
        posture_warmup: float = 0.12,
        min_velocity: float = 0.30,
        direction_ratio: float = 0.75,
    ):
        self.threshold_x = threshold_x
        self.threshold_y = threshold_y
        self.time_window = time_window
        self.cooldown = cooldown
        self.min_samples = min_samples
        self.posture_warmup = posture_warmup
        self.min_velocity = min_velocity
        self.direction_ratio = direction_ratio

        self._history = []
        self._last_swipe_time = 0.0
        self._active_side: Optional[str] = None
        self._ready_since: Optional[float] = None

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        signals = context.signals

        if signals["hand_count"] != 1:
            self._history.clear()
            self._active_side = None
            self._ready_since = None
            return []

        side = "left" if signals["left_detected"] else "right"

        two_fingers_ready = (
            signals["index_up"][side]
            and signals["middle_up"][side]
            and (not signals["ring_up"][side])
            and (not signals["pinky_up"][side])
            and (not signals["pinching"][side])
        )
        pointer = signals["pointer_position"][side]

        if not two_fingers_ready or pointer is None:
            self._history.clear()
            self._active_side = None
            self._ready_since = None
            return []

        if self._active_side is None:
            self._active_side = side
            self._ready_since = context.timestamp
            self._history.clear()
            return []
        elif self._active_side != side:
            self._history.clear()
            self._active_side = side
            self._ready_since = context.timestamp
            return []

        if self._ready_since is None:
            self._ready_since = context.timestamp
            self._history.clear()
            return []

        if (context.timestamp - self._ready_since) < self.posture_warmup:
            return []

        self._history.append({"time": context.timestamp, "x": pointer[0], "y": pointer[1]})
        self._history = [
            sample for sample in self._history if context.timestamp - sample["time"] < self.time_window
        ]

        if len(self._history) < self.min_samples:
            return []

        if (context.timestamp - self._last_swipe_time) < self.cooldown:
            return []

        event = self._build_event_from_history(side=side)
        if event is None:
            return []

        self._last_swipe_time = context.timestamp
        self._history.clear()
        return [event]

    def _build_event_from_history(self, side: str) -> Optional[GestureEvent]:
        if len(self._history) < self.min_samples:
            return None

        delta_x = self._history[-1]["x"] - self._history[0]["x"]
        delta_y = self._history[-1]["y"] - self._history[0]["y"]

        abs_dx = abs(delta_x)
        abs_dy = abs(delta_y)
        if abs_dx < self.threshold_x and abs_dy < self.threshold_y:
            return None

        duration = max(1e-6, self._history[-1]["time"] - self._history[0]["time"])
        horizontal = abs_dx >= abs_dy
        dominant_distance = abs_dx if horizontal else abs_dy
        if (dominant_distance / duration) < self.min_velocity:
            return None

        dominant_sign = -1.0 if (delta_x < 0 if horizontal else delta_y < 0) else 1.0
        if not self._is_directionally_consistent(
            history=self._history,
            horizontal=horizontal,
            expected_sign=dominant_sign,
        ):
            return None

        location: Tuple[float, float] = (self._history[-1]["x"], self._history[-1]["y"])
        if horizontal:
            if delta_x < 0:
                return GestureEvent(type=GestureType.TWO_FINGERS_SWIPE_RIGHT, hand=side, location=location)
            return GestureEvent(type=GestureType.TWO_FINGERS_SWIPE_LEFT, hand=side, location=location)

        if delta_y < 0:
            return GestureEvent(type=GestureType.TWO_FINGERS_SWIPE_UP, hand=side, location=location)
        return GestureEvent(type=GestureType.TWO_FINGERS_SWIPE_DOWN, hand=side, location=location)

    def _is_directionally_consistent(self, history, horizontal: bool, expected_sign: float) -> bool:
        matching_steps = 0
        meaningful_steps = 0

        for i in range(1, len(history)):
            dx = history[i]["x"] - history[i - 1]["x"]
            dy = history[i]["y"] - history[i - 1]["y"]
            dominant_step = dx if horizontal else dy
            orthogonal_step = dy if horizontal else dx

            if abs(dominant_step) < 0.002:
                continue

            meaningful_steps += 1
            if (dominant_step * expected_sign) > 0 and abs(dominant_step) >= abs(orthogonal_step):
                matching_steps += 1

        if meaningful_steps < 3:
            return False

        return (matching_steps / meaningful_steps) >= self.direction_ratio
