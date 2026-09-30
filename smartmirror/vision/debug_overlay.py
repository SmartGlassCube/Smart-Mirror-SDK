from collections import deque
from typing import Dict, List, Tuple

import cv2

from .gesture_types import GestureEvent
from .hand_data import HAND_CONNECTIONS, INDEX_TIP, SIDES, THUMB_TIP, HandData, Point2D

_SIDE_COLORS = {"left": (0, 220, 0), "right": (255, 180, 0)}
_PINCH_COLOR = (255, 255, 0)
_STATUS_LABELS = (("pinching", "pinch"), ("hover_posture", "hover"), ("open_hand", "open"))
_FONT = cv2.FONT_HERSHEY_SIMPLEX


class DebugOverlay:
    """Draws gesture state on camera frames: hand boxes, pointer trails, pinch span, metrics and an event feed.

    `render` shows everything in an OpenCV window (GestureDetector(debug=True)).
    `remember` + `draw(labels=False)` + `recent_events` annotate small images,
    such as the frontend's webcam preview.
    """

    def __init__(self, window_name: str = "SmartMirror Gesture Debug", trail_length: int = 24):
        self.window_name = window_name
        self._trails = {side: deque(maxlen=trail_length) for side in SIDES}
        self._event_log: deque = deque(maxlen=trail_length)

    def render(
        self,
        frame,
        hands: Dict[str, HandData],
        signals: dict,
        events: List[GestureEvent],
        now: float,
    ) -> None:
        self.remember(signals, events, now)
        self.draw(frame, hands, signals, now)
        cv2.imshow(self.window_name, frame)

    def close(self) -> None:
        cv2.destroyWindow(self.window_name)

    def remember(self, signals: dict, events: List[GestureEvent], now: float) -> None:
        """Record pointer trails and events; call once per processed frame."""
        for side in SIDES:
            pointer = signals["pointer_position"][side]
            if pointer is not None:
                self._trails[side].append(pointer)
            else:
                self._trails[side].clear()
        self._event_log.extend((now, event) for event in events)

    def recent_events(self, now: float, window: float = 2.0) -> List[GestureEvent]:
        return [event for t, event in self._event_log if now - t < window]

    def draw(self, frame, hands: Dict[str, HandData], signals: dict, now: float, labels: bool = True) -> None:
        """Draw onto `frame` in place. Sizes scale with the frame; `labels=False` skips all text."""
        h, w = frame.shape[:2]
        scale = max(w, h) / 640

        for side in SIDES:
            self._draw_hand(frame, side, hands[side], signals, w, h, scale, labels)

        if not labels:
            return

        _text(frame, f"hands={signals['hand_count']}", (10, 20), 0.6, (255, 255, 255), thickness=2)
        for i, event in enumerate(self.recent_events(now)[-8:]):
            label = event.name.replace("_", " ") + (f" [{event.hand}]" if event.hand else "")
            _text(frame, label, (10, 45 + 18 * i), 0.5, (50, 220, 255))

    def _draw_hand(self, frame, side, hand: HandData, signals, w, h, scale, labels) -> None:
        color = _SIDE_COLORS[side]
        thin = max(1, round(scale))
        thick = max(2, round(2 * scale))  # stays visible on small previews
        pinching = signals["pinching"][side]

        if hand.landmarks is not None:
            points = [_to_px(landmark, w, h) for landmark in hand.landmarks]
            for start, end in HAND_CONNECTIONS:
                cv2.line(frame, points[start], points[end], color, thin, cv2.LINE_AA)

        pointer = signals["pointer_position"][side]
        if pointer is not None:
            radius = max(2, round(7 * scale))
            cv2.circle(frame, _to_px(pointer, w, h), radius, color, cv2.FILLED if pinching else thick)

        trail = list(self._trails[side])
        for i in range(1, len(trail)):
            cv2.line(frame, _to_px(trail[i - 1], w, h), _to_px(trail[i], w, h), color, thin if i < len(trail) // 2 else thick)

        if hand.bbox is None:
            return

        x_min, y_min, x_max, y_max = hand.bbox
        p1 = (int(x_min * w), int(y_min * h))
        p2 = (int(x_max * w), int(y_max * h))
        cv2.rectangle(frame, p1, p2, color, thick)

        # thumb-index span, used by pinch and zoom
        thumb, index = hand.landmarks[THUMB_TIP], hand.landmarks[INDEX_TIP]
        cv2.line(
            frame, _to_px(thumb, w, h), _to_px(index, w, h),
            _PINCH_COLOR if pinching else (230, 230, 230), thick if pinching else thin,
        )

        if labels:
            self._draw_hand_labels(frame, side, signals, p1, p2, color)

    def _draw_hand_labels(self, frame, side, signals, p1, p2, color) -> None:
        status = [label for signal, label in _STATUS_LABELS if signals[signal][side]]
        _text(frame, f"{side}: {'|'.join(status) or 'idle'}", (p1[0], max(20, p1[1] - 8)), 0.5, color)

        span = signals["thumb_index_distance"][side]
        span_delta = signals["thumb_index_distance_delta"][side]
        if span is not None:
            span_label = f"span:{span:.3f}" + (f" d:{span_delta:+.3f}" if span_delta is not None else "")
            _text(frame, span_label, (p1[0], p2[1] + 16), 0.45, (220, 220, 220))

        info_lines = []
        pointer_delta = signals["pointer_delta"][side]
        if signals["pinching"][side] and pointer_delta is not None:
            info_lines.append(f"drag dx:{pointer_delta[0]:+.3f} dy:{pointer_delta[1]:+.3f}")
        if signals["zoom_mode_pinky_up"][side]:
            info_lines.append("zoom mode: pinky")
        if signals["zoom_mode_no_pinky"][side]:
            info_lines.append("zoom mode: no-pinky")
        vy = signals["vertical_delta"][side]
        if signals["hover_posture"][side] and vy is not None:
            info_lines.append(f"scroll vy:{vy:+.3f}")

        for i, line in enumerate(info_lines[:2]):
            _text(frame, line, (p1[0], p2[1] + 34 + 16 * i), 0.42, color)


def _to_px(point: Point2D, w: int, h: int) -> Tuple[int, int]:
    return (int(point[0] * w), int(point[1] * h))


def _text(frame, text, origin, scale, color, thickness=1) -> None:
    cv2.putText(frame, text, origin, _FONT, scale, color, thickness, cv2.LINE_AA)
