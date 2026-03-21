from typing import List, Optional

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import HandData
from .base import DynamicGesture, GestureContext


class SwipeGesture(DynamicGesture):
    name = "swipe"

    def __init__(
        self,
        threshold_x: float = 0.12,
        threshold_y: float = 0.12,
        time_window: float = 0.50,
        cooldown: float = 0.60,
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

        self._history = {"left": [], "right": []}
        self._ready_since = {"left": None, "right": None}
        self._last_swipe_time = 0.0

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        events: List[GestureEvent] = []

        signals = context.signals
        hand_count = signals["hand_count"]

        if hand_count == 1:
            active_side = "left" if signals["left_detected"] else "right"
            if (
                signals["open_hand"][active_side]
                and not signals["pinching"][active_side]
            ):
                if self._ready_since[active_side] is None:
                    self._ready_since[active_side] = context.timestamp
                    self._history[active_side].clear()
                    return events

                if (context.timestamp - self._ready_since[active_side]) < self.posture_warmup:
                    return events

                swipe_event = self._detect_swipe(
                    hand=context.hands[active_side],
                    side=active_side,
                    current_time=context.timestamp,
                )
                if (
                    swipe_event is not None
                    and (context.timestamp - self._last_swipe_time) > self.cooldown
                ):
                    events.append(swipe_event)
                    self._last_swipe_time = context.timestamp
            else:
                self._history[active_side].clear()
                self._ready_since[active_side] = None
        else:
            self._history["left"].clear()
            self._history["right"].clear()
            self._ready_since["left"] = None
            self._ready_since["right"] = None

        return events

    def _detect_swipe(
        self,
        hand: HandData,
        side: str,
        current_time: float,
    ) -> Optional[GestureEvent]:
        if hand.landmarks is None or hand.palm_center is None:
            self._history[side].clear()
            return None

        self._history[side].append(
            {
                "time": current_time,
                "x": hand.palm_center[0],
                "y": hand.palm_center[1],
            }
        )

        self._history[side] = [
            entry
            for entry in self._history[side]
            if current_time - entry["time"] < self.time_window
        ]

        history = self._history[side]
        if len(history) < self.min_samples:
            return None

        delta_x = history[-1]["x"] - history[0]["x"]
        delta_y = history[-1]["y"] - history[0]["y"]

        abs_dx = abs(delta_x)
        abs_dy = abs(delta_y)

        if abs_dx < self.threshold_x and abs_dy < self.threshold_y:
            return None

        duration = max(1e-6, history[-1]["time"] - history[0]["time"])
        horizontal = abs_dx >= abs_dy
        dominant_distance = abs_dx if horizontal else abs_dy
        if (dominant_distance / duration) < self.min_velocity:
            return None

        dominant_sign = -1.0 if (delta_x < 0 if horizontal else delta_y < 0) else 1.0
        if not self._is_directionally_consistent(
            history=history,
            horizontal=horizontal,
            expected_sign=dominant_sign,
        ):
            return None

        location = (history[-1]["x"], history[-1]["y"])
        self._history[side].clear()

        if horizontal:
            if delta_x < 0:
                return GestureEvent(type=GestureType.SWIPE_RIGHT, hand=side, location=location)
            return GestureEvent(type=GestureType.SWIPE_LEFT, hand=side, location=location)

        if delta_y < 0:
            return GestureEvent(type=GestureType.SWIPE_UP, hand=side, location=location)
        return GestureEvent(type=GestureType.SWIPE_DOWN, hand=side, location=location)

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