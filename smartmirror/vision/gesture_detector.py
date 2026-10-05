import math
import time
from typing import Dict, List, Optional

from .debug_overlay import DebugOverlay
from .gesture_types import GestureEvent
from .gestures.base import Gesture, GestureContext
from .gestures.default_set import default_gesture_set
from .hand_data import (
    INDEX_PIP,
    INDEX_TIP,
    MIDDLE_PIP,
    MIDDLE_TIP,
    PINKY_PIP,
    PINKY_TIP,
    RING_PIP,
    RING_TIP,
    SIDES,
    THUMB_TIP,
    HandData,
    Point2D,
)
from .landmark_detector import LandmarkDetector


class GestureDetector:
    """Orchestrates the vision pipeline for one frame.

    1. `LandmarkDetector` extracts left/right `HandData`.
    2. Shared per-frame `signals` are computed once (see `_build_signals`).
    3. Every configured `Gesture` runs on a `GestureContext` and returns events.

    `process_frame` returns `{"hands": ..., "signals": ..., "events": [...]}`.
    """

    def __init__(
        self,
        landmark_detector: Optional[LandmarkDetector] = None,
        gestures: Optional[List[Gesture]] = None,
        debug: bool = False,
        debug_window_name: str = "SmartMirror Gesture Debug",
        pinch_start_threshold: float = 0.045,
        pinch_end_threshold: float = 0.065,
        zoom_min_span: float = 0.08,
    ):
        self.landmark_detector = landmark_detector  # created on first process_frame if None
        self.gestures: List[Gesture] = default_gesture_set() if gestures is None else list(gestures)
        self.pinch_start_threshold = pinch_start_threshold
        self.pinch_end_threshold = pinch_end_threshold
        self.zoom_min_span = zoom_min_span
        self.overlay = DebugOverlay(window_name=debug_window_name) if debug else None

        self._was_pinching = {side: False for side in SIDES}
        self._prev_pointer: Dict[str, Optional[Point2D]] = {side: None for side in SIDES}
        self._prev_span: Dict[str, Optional[float]] = {side: None for side in SIDES}

    @property
    def debug(self) -> bool:
        return self.overlay is not None

    def add_gesture(self, gesture: Gesture) -> None:
        self.gestures.append(gesture)

    def process_frame(self, frame) -> dict:
        if self.landmark_detector is None:
            self.landmark_detector = LandmarkDetector()
        hands = self.landmark_detector.extract_hands(frame)
        return self.process_hands(hands, frame=frame)

    def process_hands(self, hands: Dict[str, HandData], frame=None, timestamp: Optional[float] = None) -> dict:
        """Run the gestures on already-extracted hands (e.g. from another tracker or a recording)."""
        now = time.time() if timestamp is None else timestamp
        signals = self._build_signals(hands)
        context = GestureContext(hands=hands, signals=signals, timestamp=now)

        events: List[GestureEvent] = []
        for gesture in self.gestures:
            events.extend(gesture.detect(context))

        for side in SIDES:
            self._was_pinching[side] = signals["pinching"][side]
            self._prev_pointer[side] = signals["pointer_position"][side]
            self._prev_span[side] = signals["thumb_index_distance"][side]

        if self.overlay is not None and frame is not None:
            self.overlay.render(frame=frame, hands=hands, signals=signals, events=events, now=now)

        return {"hands": hands, "signals": signals, "events": events}

    def close(self) -> None:
        if self.overlay is not None:
            self.overlay.close()

    def _build_signals(self, hands: Dict[str, HandData]) -> dict:
        def per_side(fn):
            return {side: fn(side) for side in SIDES}

        def finger_up(tip_idx, pip_idx):
            return per_side(lambda side: _is_finger_up(hands[side], tip_idx, pip_idx))

        span = per_side(lambda side: _thumb_index_distance(hands[side]))
        pinching = per_side(lambda side: self._is_pinching(span[side], self._was_pinching[side]))
        index_up = finger_up(INDEX_TIP, INDEX_PIP)
        middle_up = finger_up(MIDDLE_TIP, MIDDLE_PIP)
        ring_up = finger_up(RING_TIP, RING_PIP)
        pinky_up = finger_up(PINKY_TIP, PINKY_PIP)
        pointer = per_side(lambda side: _pointer_position(hands[side]))
        pointer_delta = per_side(lambda side: _point_delta(self._prev_pointer[side], pointer[side]))

        def zoom_mode(require_pinky):
            return per_side(
                lambda side: span[side] is not None
                and not pinching[side]
                and pinky_up[side] == require_pinky
                and span[side] >= self.zoom_min_span
            )

        left_detected = hands["left"].detected
        right_detected = hands["right"].detected

        return {
            "hand_count": int(left_detected) + int(right_detected),
            "left_detected": left_detected,
            "right_detected": right_detected,
            "pinching": pinching,
            "index_up": index_up,
            "middle_up": middle_up,
            "ring_up": ring_up,
            "pinky_up": pinky_up,
            "hover_posture": per_side(lambda side: index_up[side] and middle_up[side]),
            "open_hand": per_side(
                lambda side: sum([index_up[side], middle_up[side], ring_up[side], pinky_up[side]]) >= 3
                and not pinching[side]
            ),
            "both_hands_raised": hands["left"].is_raised and hands["right"].is_raised,
            "pointer_position": pointer,
            "pointer_delta": pointer_delta,
            "horizontal_delta": per_side(lambda side: None if pointer_delta[side] is None else pointer_delta[side][0]),
            "vertical_delta": per_side(lambda side: None if pointer_delta[side] is None else pointer_delta[side][1]),
            "thumb_index_distance": span,
            "thumb_index_distance_delta": per_side(
                lambda side: None
                if span[side] is None or self._prev_span[side] is None
                else span[side] - self._prev_span[side]
            ),
            "zoom_mode_pinky_up": zoom_mode(require_pinky=True),
            "zoom_mode_no_pinky": zoom_mode(require_pinky=False),
        }

    def _is_pinching(self, span: Optional[float], was_pinching: bool) -> bool:
        # Hysteresis: easier to keep a pinch than to start one.
        if span is None:
            return False
        return span < (self.pinch_end_threshold if was_pinching else self.pinch_start_threshold)


def _thumb_index_distance(hand: HandData) -> Optional[float]:
    if not hand.detected:
        return None
    thumb, index = hand.landmarks[THUMB_TIP], hand.landmarks[INDEX_TIP]
    return math.hypot(thumb[0] - index[0], thumb[1] - index[1])


def _is_finger_up(hand: HandData, tip_idx: int, pip_idx: int) -> bool:
    return hand.detected and hand.landmarks[tip_idx][1] < hand.landmarks[pip_idx][1]


def _pointer_position(hand: HandData) -> Optional[Point2D]:
    if hand.detected:
        index_tip = hand.landmarks[INDEX_TIP]
        return (index_tip[0], index_tip[1])
    return hand.palm_center


def _point_delta(previous: Optional[Point2D], current: Optional[Point2D]) -> Optional[Point2D]:
    if previous is None or current is None:
        return None
    return (current[0] - previous[0], current[1] - previous[1])
