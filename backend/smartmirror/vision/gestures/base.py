from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from ..gesture_types import GestureEvent, GestureType
from ..hand_data import HandData, Point2D

EventName = Union[GestureType, str]


@dataclass
class GestureContext:
    hands: Dict[str, HandData]
    signals: Dict[str, Any]
    timestamp: float


class Gesture(ABC):
    """One gesture = one class. `detect` runs once per frame and returns the events it fired."""

    name = "gesture"

    @abstractmethod
    def detect(self, context: GestureContext) -> List[GestureEvent]:
        raise NotImplementedError

    def reset(self) -> None:
        return None


class ContinuousGesture(Gesture):
    """Base for gestures with a start -> update* -> end lifecycle (scroll, zoom, ...).

    Call `_phase` once per hand per frame; it emits the right event and keeps
    the active/inactive state per `(channel, side)`.
    """

    def __init__(self):
        self._active: Dict[Tuple[str, str], bool] = {}

    def reset(self) -> None:
        self._active.clear()

    def _phase(
        self,
        side: str,
        triggered: bool,
        ended: bool,
        events: Tuple[EventName, EventName, EventName],
        location: Optional[Point2D],
        data: Optional[Dict[str, Any]] = None,
        end_data: Optional[Dict[str, Any]] = None,
        channel: str = "default",
    ) -> List[GestureEvent]:
        start, update, end = events
        key = (channel, side)
        active = self._active.get(key, False)

        if triggered:
            self._active[key] = True
            return [GestureEvent(type=update if active else start, hand=side, location=location, data=data)]

        if active and ended:
            self._active[key] = False
            return [GestureEvent(type=end, hand=side, location=location, data=end_data)]

        return []


class PostureSwipeGesture(Gesture):
    """Base for one-hand swipes performed while holding a posture.

    Subclasses define the posture (`is_ready`), the tracked point
    (`tracked_point`) and the emitted event per direction (`directions`).
    Because the camera frame is mirrored, moving the hand toward screen-left
    produces the "right" direction.
    """

    directions: Dict[str, EventName] = {}

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

        self._history: List[Tuple[float, float, float]] = []  # (time, x, y)
        self._active_side: Optional[str] = None
        self._ready_since: Optional[float] = None
        self._last_swipe_time = float("-inf")

    @abstractmethod
    def is_ready(self, context: GestureContext, side: str) -> bool:
        """True while the hand holds the posture that arms this swipe."""

    @abstractmethod
    def tracked_point(self, context: GestureContext, side: str) -> Optional[Point2D]:
        """The point whose motion is measured (palm center, fingertip, ...)."""

    def reset(self) -> None:
        self._history.clear()
        self._active_side = None
        self._ready_since = None

    def detect(self, context: GestureContext) -> List[GestureEvent]:
        if context.signals["hand_count"] != 1:
            self.reset()
            return []

        side = "left" if context.signals["left_detected"] else "right"
        point = self.tracked_point(context, side)
        if point is None or not self.is_ready(context, side):
            self.reset()
            return []

        now = context.timestamp
        if self._active_side != side:
            self.reset()
            self._active_side = side
            self._ready_since = now
            return []

        if now - self._ready_since < self.posture_warmup:
            return []

        self._history.append((now, point[0], point[1]))
        self._history = [sample for sample in self._history if now - sample[0] < self.time_window]

        direction = self._classify(self._history)
        if direction is None:
            return []

        # Clear even when cooling down, so the hand's return motion isn't read as a swipe back.
        self._history.clear()
        if now - self._last_swipe_time <= self.cooldown:
            return []

        self._last_swipe_time = now
        return [GestureEvent(type=self.directions[direction], hand=side, location=point)]

    def _classify(self, history: List[Tuple[float, float, float]]) -> Optional[str]:
        if len(history) < self.min_samples:
            return None

        start_time, start_x, start_y = history[0]
        end_time, end_x, end_y = history[-1]
        delta_x = end_x - start_x
        delta_y = end_y - start_y

        if abs(delta_x) < self.threshold_x and abs(delta_y) < self.threshold_y:
            return None

        horizontal = abs(delta_x) >= abs(delta_y)
        dominant = delta_x if horizontal else delta_y
        duration = max(1e-6, end_time - start_time)
        if abs(dominant) / duration < self.min_velocity:
            return None

        if not self._is_directionally_consistent(history, horizontal, 1.0 if dominant > 0 else -1.0):
            return None

        if horizontal:
            return "right" if delta_x < 0 else "left"
        return "up" if delta_y < 0 else "down"

    def _is_directionally_consistent(self, history, horizontal: bool, expected_sign: float) -> bool:
        matching_steps = 0
        meaningful_steps = 0

        for (_, x0, y0), (_, x1, y1) in zip(history, history[1:]):
            dx, dy = x1 - x0, y1 - y0
            dominant_step, orthogonal_step = (dx, dy) if horizontal else (dy, dx)

            if abs(dominant_step) < 0.002:
                continue

            meaningful_steps += 1
            if dominant_step * expected_sign > 0 and abs(dominant_step) >= abs(orthogonal_step):
                matching_steps += 1

        if meaningful_steps < 3:
            return False

        return matching_steps / meaningful_steps >= self.direction_ratio
