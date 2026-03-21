import math
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

import cv2

from .landmark_detector import LandmarkDetector
from .gesture_types import GestureEvent
from .gestures.base import Gesture, GestureContext
from .gestures.default_set import default_gesture_set
from .hand_data import HandData


class GestureDetector:
    """
    Modular CV-side gesture detector.

    Responsibilities:
    - call LandmarkDetector
    - compute continuous signals
    - execute configured Gesture objects
    - optionally render debug overlay

    Return format:
        {
            "hands": ...,
            "signals": ...,
            "events": ...
        }
    """

    PINCH_START_THRESHOLD = 0.045
    PINCH_END_THRESHOLD = 0.065
    ZOOM_MIN_SPAN = 0.08

    def __init__(
        self,
        landmark_detector: Optional[LandmarkDetector] = None,
        gestures: Optional[List[Gesture]] = None,
        debug: bool = False,
        debug_window_name: str = "SmartMirror Gesture Debug",
    ):
        self.landmark_detector = landmark_detector or LandmarkDetector()
        self.gestures: List[Gesture] = gestures or default_gesture_set()

        self.debug = debug
        self.debug_window_name = debug_window_name

        self._pinch_signal_state = {"left": False, "right": False}
        self._prev_pointer_position: Dict[str, Optional[Tuple[float, float]]] = {
            "left": None,
            "right": None,
        }
        self._prev_thumb_index_distance: Dict[str, Optional[float]] = {
            "left": None,
            "right": None,
        }
        self._pointer_history = {
            "left": deque(maxlen=24),
            "right": deque(maxlen=24),
        }
        self._event_log = deque(maxlen=24)

    def process_frame(self, frame) -> dict:
        hands = self.landmark_detector.extract_hands(frame)
        return self.process_hands(hands, frame=frame)

    def process_hands(self, hands: Dict[str, HandData], frame=None) -> dict:
        now = time.time()

        signals = self._build_signals(hands)
        context = GestureContext(hands=hands, signals=signals, timestamp=now)

        events: List[GestureEvent] = []
        for gesture in self.gestures:
            events.extend(gesture.detect(context))

        for event in events:
            self._event_log.append((now, event))

        self._event_log = deque(
            [(t, event) for t, event in self._event_log if now - t < 3.0],
            maxlen=24,
        )

        self._update_memory(signals)

        if self.debug and frame is not None:
            self._render_debug(frame=frame, hands=hands, signals=signals, events=events)

        return {
            "hands": hands,
            "signals": signals,
            "events": events,
        }

    def _build_signals(self, hands: Dict[str, HandData]) -> dict:
        left_detected = hands["left"].landmarks is not None
        right_detected = hands["right"].landmarks is not None
        hand_count = int(left_detected) + int(right_detected)

        pinching = {
            "left": self._is_pinching(hands["left"], self._pinch_signal_state["left"]),
            "right": self._is_pinching(hands["right"], self._pinch_signal_state["right"]),
        }

        index_up = {
            "left": self._is_finger_up(hands["left"], tip_idx=8, pip_idx=6),
            "right": self._is_finger_up(hands["right"], tip_idx=8, pip_idx=6),
        }
        middle_up = {
            "left": self._is_finger_up(hands["left"], tip_idx=12, pip_idx=10),
            "right": self._is_finger_up(hands["right"], tip_idx=12, pip_idx=10),
        }
        ring_up = {
            "left": self._is_finger_up(hands["left"], tip_idx=16, pip_idx=14),
            "right": self._is_finger_up(hands["right"], tip_idx=16, pip_idx=14),
        }
        pinky_up = {
            "left": self._is_finger_up(hands["left"], tip_idx=20, pip_idx=18),
            "right": self._is_finger_up(hands["right"], tip_idx=20, pip_idx=18),
        }

        hover_posture = {
            side: index_up[side] and middle_up[side]
            for side in ("left", "right")
        }

        open_hand = {
            side: self._count_true(
                [
                    index_up[side],
                    middle_up[side],
                    ring_up[side],
                    pinky_up[side],
                ]
            ) >= 3 and not pinching[side]
            for side in ("left", "right")
        }

        pointer_position = {
            "left": self._pointer_position(hands["left"]),
            "right": self._pointer_position(hands["right"]),
        }

        pointer_delta = {
            "left": self._point_delta(self._prev_pointer_position["left"], pointer_position["left"]),
            "right": self._point_delta(self._prev_pointer_position["right"], pointer_position["right"]),
        }

        thumb_index_distance = {
            "left": self._thumb_index_distance(hands["left"]),
            "right": self._thumb_index_distance(hands["right"]),
        }

        thumb_index_distance_delta = {
            "left": self._scalar_delta(self._prev_thumb_index_distance["left"], thumb_index_distance["left"]),
            "right": self._scalar_delta(self._prev_thumb_index_distance["right"], thumb_index_distance["right"]),
        }

        horizontal_delta = {
            "left": None if pointer_delta["left"] is None else pointer_delta["left"][0],
            "right": None if pointer_delta["right"] is None else pointer_delta["right"][0],
        }

        vertical_delta = {
            "left": None if pointer_delta["left"] is None else pointer_delta["left"][1],
            "right": None if pointer_delta["right"] is None else pointer_delta["right"][1],
        }

        zoom_mode_pinky_up = {
            side: self._is_zoom_mode(
                span=thumb_index_distance[side],
                pinching=pinching[side],
                pinky_up=pinky_up[side],
                require_pinky=True,
            )
            for side in ("left", "right")
        }

        zoom_mode_no_pinky = {
            side: self._is_zoom_mode(
                span=thumb_index_distance[side],
                pinching=pinching[side],
                pinky_up=pinky_up[side],
                require_pinky=False,
            )
            for side in ("left", "right")
        }

        return {
            "hand_count": hand_count,
            "left_detected": left_detected,
            "right_detected": right_detected,
            "pinching": pinching,
            "index_up": index_up,
            "middle_up": middle_up,
            "ring_up": ring_up,
            "pinky_up": pinky_up,
            "hover_posture": hover_posture,
            "open_hand": open_hand,
            "both_hands_raised": hands["left"].is_raised and hands["right"].is_raised,
            "pointer_position": pointer_position,
            "pointer_delta": pointer_delta,
            "horizontal_delta": horizontal_delta,
            "vertical_delta": vertical_delta,
            "thumb_index_distance": thumb_index_distance,
            "thumb_index_distance_delta": thumb_index_distance_delta,
            "zoom_mode_pinky_up": zoom_mode_pinky_up,
            "zoom_mode_no_pinky": zoom_mode_no_pinky,
        }

    def _update_memory(self, signals: dict) -> None:
        for side in ("left", "right"):
            self._pinch_signal_state[side] = signals["pinching"][side]
            self._prev_pointer_position[side] = signals["pointer_position"][side]
            self._prev_thumb_index_distance[side] = signals["thumb_index_distance"][side]

            pointer = signals["pointer_position"][side]
            if pointer is not None:
                self._pointer_history[side].append(pointer)
            elif self._pointer_history[side]:
                self._pointer_history[side].clear()

    def close(self) -> None:
        if self.debug:
            cv2.destroyWindow(self.debug_window_name)

    def _render_debug(
        self,
        frame,
        hands: Dict[str, HandData],
        signals: dict,
        events: List[GestureEvent],
    ) -> None:
        h, w = frame.shape[:2]
        now = time.time()

        for side in ("left", "right"):
            hand = hands[side]
            color = (0, 220, 0) if side == "left" else (255, 180, 0)

            pointer = signals["pointer_position"][side]
            if pointer is not None:
                center = self._norm_to_px(pointer, w, h)
                cv2.circle(frame, center, 7, color, 2)

            history = list(self._pointer_history[side])
            for i in range(1, len(history)):
                p1 = self._norm_to_px(history[i - 1], w, h)
                p2 = self._norm_to_px(history[i], w, h)
                thickness = 1 if i < len(history) // 2 else 2
                cv2.line(frame, p1, p2, color, thickness)

            if hand.bbox is None:
                continue

            x_min, y_min, x_max, y_max = hand.bbox
            p1 = (int(x_min * w), int(y_min * h))
            p2 = (int(x_max * w), int(y_max * h))
            cv2.rectangle(frame, p1, p2, color, 2)

            status = []
            if signals["pinching"][side]:
                status.append("pinch")
            if signals["hover_posture"][side]:
                status.append("hover")
            if signals["open_hand"][side]:
                status.append("open")

            label = f"{side}: {'|'.join(status) if status else 'idle'}"
            cv2.putText(
                frame,
                label,
                (p1[0], max(20, p1[1] - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

            # thumb-index span visualization for pinch/zoom follow-through
            if hand.landmarks is not None:
                thumb = hand.landmarks[4]
                index = hand.landmarks[8]
                thumb_px = self._norm_to_px((thumb[0], thumb[1]), w, h)
                index_px = self._norm_to_px((index[0], index[1]), w, h)
                cv2.line(frame, thumb_px, index_px, (230, 230, 230), 1)
                span = signals["thumb_index_distance"][side]
                span_delta = signals["thumb_index_distance_delta"][side]
                if span is not None:
                    span_label = f"span:{span:.3f}"
                    if span_delta is not None:
                        span_label += f" d:{span_delta:+.3f}"
                    cv2.putText(
                        frame,
                        span_label,
                        (p1[0], p2[1] + 16),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (220, 220, 220),
                        1,
                        cv2.LINE_AA,
                    )

            info_lines = []
            pd = signals["pointer_delta"][side]
            if signals["pinching"][side] and pd is not None:
                info_lines.append(f"drag dx:{pd[0]:+.3f} dy:{pd[1]:+.3f}")

            if signals["zoom_mode_pinky_up"][side]:
                info_lines.append("zoom mode: pinky")
            if signals["zoom_mode_no_pinky"][side]:
                info_lines.append("zoom mode: no-pinky")

            vy = signals["vertical_delta"][side]
            if signals["hover_posture"][side] and vy is not None:
                info_lines.append(f"scroll vy:{vy:+.3f}")

            text_y = p2[1] + 34
            for line in info_lines[:2]:
                cv2.putText(
                    frame,
                    line,
                    (p1[0], text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    color,
                    1,
                    cv2.LINE_AA,
                )
                text_y += 16

        cv2.putText(
            frame,
            f"hands={signals['hand_count']}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        y = 45
        recent_events = [(t, e) for t, e in self._event_log if now - t < 2.0]
        for _, event in recent_events[-8:]:
            event_text = event.type.value.replace("_", " ")
            if event.hand:
                event_text = f"{event_text} [{event.hand}]"
            cv2.putText(
                frame,
                event_text,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (50, 220, 255),
                1,
                cv2.LINE_AA,
            )
            y += 18

        cv2.imshow(self.debug_window_name, frame)

    def _norm_to_px(self, point: Tuple[float, float], w: int, h: int) -> Tuple[int, int]:
        return (int(point[0] * w), int(point[1] * h))

    def _count_true(self, values: List[bool]) -> int:
        return sum(1 for value in values if value)

    def _is_pinching(self, hand: HandData, was_pinching: bool) -> bool:
        distance = self._thumb_index_distance(hand)
        if distance is None:
            return False

        if was_pinching:
            return distance < self.PINCH_END_THRESHOLD
        return distance < self.PINCH_START_THRESHOLD

    def _is_zoom_mode(
        self,
        span: Optional[float],
        pinching: bool,
        pinky_up: bool,
        require_pinky: bool,
    ) -> bool:
        if span is None or pinching:
            return False

        if require_pinky and not pinky_up:
            return False

        if not require_pinky and pinky_up:
            return False

        return span >= self.ZOOM_MIN_SPAN

    def _thumb_index_distance(self, hand: HandData) -> Optional[float]:
        if hand.landmarks is None:
            return None

        thumb_tip = hand.landmarks[4]
        index_tip = hand.landmarks[8]

        dx = thumb_tip[0] - index_tip[0]
        dy = thumb_tip[1] - index_tip[1]
        return math.sqrt(dx * dx + dy * dy)

    def _is_finger_up(self, hand: HandData, tip_idx: int, pip_idx: int) -> bool:
        if hand.landmarks is None:
            return False

        return hand.landmarks[tip_idx][1] < hand.landmarks[pip_idx][1]

    def _pointer_position(self, hand: HandData):
        if hand.landmarks is not None:
            index_tip = hand.landmarks[8]
            return (index_tip[0], index_tip[1])
        return hand.palm_center

    def _point_delta(self, prev_point, current_point):
        if prev_point is None or current_point is None:
            return None

        return (
            current_point[0] - prev_point[0],
            current_point[1] - prev_point[1],
        )

    def _scalar_delta(self, prev_value, current_value):
        if prev_value is None or current_value is None:
            return None
        return current_value - prev_value
