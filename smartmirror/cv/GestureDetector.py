import math
import time
from typing import Dict, List, Optional

from .LandmarkDetector import LandmarkDetector
from .gesture_types import GestureType, GestureEvent
from .hand_data import HandData


class GestureDetector:
    """
    CV-side gesture detector.

    Responsibilities:
    - call LandmarkDetector
    - compute continuous signals
    - detect transition events
    - return:
        {
            "hands": ...,
            "signals": ...,
            "events": ...
        }

    Current implemented families:
    - pinch start / end
    - 4-direction swipe
    - hover posture
    - left click / right click
    - scroll start / end
    - one-hand zoom start / end
    - open hand detection
    - pointer position / deltas
    """

    # --------------------------
    # Thresholds
    # --------------------------

    # Pinch hysteresis
    PINCH_START_THRESHOLD = 0.045
    PINCH_END_THRESHOLD = 0.065

    # Swipe
    SWIPE_THRESHOLD_X = 0.18
    SWIPE_THRESHOLD_Y = 0.18
    SWIPE_TIME_WINDOW = 0.35
    SWIPE_COOLDOWN = 0.60
    MIN_SWIPE_SAMPLES = 5

    # Scroll (gentler than swipe)
    SCROLL_START_DELTA_Y = 0.05
    SCROLL_END_DELTA_Y = 0.02

    # Zoom
    ZOOM_MIN_SPAN = 0.08
    ZOOM_START_DELTA = 0.025
    ZOOM_END_DELTA = 0.015

    def __init__(self, landmark_detector: Optional[LandmarkDetector] = None):
        self.landmark_detector = landmark_detector or LandmarkDetector()

        # State memory
        self.pinch_state = {"left": False, "right": False}
        self.scroll_state = {"left": False, "right": False}
        self.zoom_state_pinky_up = {"left": False, "right": False}
        self.zoom_state_no_pinky = {"left": False, "right": False}

        self.prev_index_up = {"left": False, "right": False}
        self.prev_middle_up = {"left": False, "right": False}
        self.prev_hover_posture = {"left": False, "right": False}

        self.prev_pointer_position = {"left": None, "right": None}
        self.prev_thumb_index_distance = {"left": None, "right": None}

        self.hand_history = {"left": [], "right": []}
        self.last_swipe_time = 0.0

    def process_frame(self, frame) -> dict:
        hands = self.landmark_detector.extract_hands(frame)
        return self.process_hands(hands)

    def process_hands(self, hands: Dict[str, HandData]) -> dict:
        current_time = time.time()
        events: List[GestureEvent] = []

        left_detected = hands["left"].landmarks is not None
        right_detected = hands["right"].landmarks is not None
        hand_count = int(left_detected) + int(right_detected)

        # --------------------------
        # Per-hand posture signals
        # --------------------------

        current_pinching = {
            "left": self._is_pinching(hands["left"], self.pinch_state["left"]),
            "right": self._is_pinching(hands["right"], self.pinch_state["right"]),
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
            ) >= 3 and not current_pinching[side]
            for side in ("left", "right")
        }

        pointer_position = {
            "left": self._pointer_position(hands["left"]),
            "right": self._pointer_position(hands["right"]),
        }

        pointer_delta = {
            "left": self._point_delta(self.prev_pointer_position["left"], pointer_position["left"]),
            "right": self._point_delta(self.prev_pointer_position["right"], pointer_position["right"]),
        }

        thumb_index_distance = {
            "left": self._thumb_index_distance(hands["left"]),
            "right": self._thumb_index_distance(hands["right"]),
        }

        thumb_index_distance_delta = {
            "left": self._scalar_delta(
                self.prev_thumb_index_distance["left"],
                thumb_index_distance["left"],
            ),
            "right": self._scalar_delta(
                self.prev_thumb_index_distance["right"],
                thumb_index_distance["right"],
            ),
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
            side: (
                thumb_index_distance[side] is not None
                and thumb_index_distance[side] >= self.ZOOM_MIN_SPAN
                and not current_pinching[side]
                and pinky_up[side]
            )
            for side in ("left", "right")
        }

        zoom_mode_no_pinky = {
            side: (
                thumb_index_distance[side] is not None
                and thumb_index_distance[side] >= self.ZOOM_MIN_SPAN
                and not current_pinching[side]
                and not pinky_up[side]
            )
            for side in ("left", "right")
        }

        # --------------------------
        # Events: pinch start / end
        # --------------------------
        for side in ("left", "right"):
            if current_pinching[side] and not self.pinch_state[side]:
                events.append(GestureEvent(type=GestureType.PINCH_START, hand=side))
            elif not current_pinching[side] and self.pinch_state[side]:
                events.append(GestureEvent(type=GestureType.PINCH_END, hand=side))

            self.pinch_state[side] = current_pinching[side]

        # --------------------------
        # Events: click detection
        # Rule:
        # - hover posture existed previously
        # - left click: index goes down while middle stays up
        # - right click: middle goes down while index stays up
        # --------------------------
        for side in ("left", "right"):
            if self.prev_hover_posture[side]:
                if self.prev_index_up[side] and not index_up[side] and middle_up[side]:
                    events.append(GestureEvent(type=GestureType.LEFT_CLICK, hand=side))
                elif self.prev_middle_up[side] and not middle_up[side] and index_up[side]:
                    events.append(GestureEvent(type=GestureType.RIGHT_CLICK, hand=side))

        # --------------------------
        # Events: scroll detection
        # Rule:
        # - only meaningful while hover posture is active
        # - gentle vertical motion starts scroll
        # - losing hover or very small motion ends scroll
        # --------------------------
        for side in ("left", "right"):
            vy = vertical_delta[side]

            if hover_posture[side] and vy is not None and abs(vy) >= self.SCROLL_START_DELTA_Y:
                if not self.scroll_state[side]:
                    events.append(GestureEvent(type=GestureType.SCROLL_START, hand=side))
                    self.scroll_state[side] = True
            else:
                if self.scroll_state[side]:
                    if (not hover_posture[side]) or (vy is None) or (abs(vy) <= self.SCROLL_END_DELTA_Y):
                        events.append(GestureEvent(type=GestureType.SCROLL_END, hand=side))
                        self.scroll_state[side] = False

        # --------------------------
        # Events: zoom detection
        # One-hand zoom:
        # - based on thumb-index span
        # - pinky_up distinguishes mode
        # - uses delta of thumb-index distance
        # --------------------------
        for side in ("left", "right"):
            span_delta = thumb_index_distance_delta[side]

            # Zoom with pinky up
            if zoom_mode_pinky_up[side] and span_delta is not None and abs(span_delta) >= self.ZOOM_START_DELTA:
                if not self.zoom_state_pinky_up[side]:
                    events.append(GestureEvent(type=GestureType.ZOOM_START_PINKY_UP, hand=side))
                    self.zoom_state_pinky_up[side] = True
            else:
                if self.zoom_state_pinky_up[side]:
                    if (not zoom_mode_pinky_up[side]) or (span_delta is None) or (abs(span_delta) <= self.ZOOM_END_DELTA):
                        events.append(GestureEvent(type=GestureType.ZOOM_END_PINKY_UP, hand=side))
                        self.zoom_state_pinky_up[side] = False

            # Zoom with no pinky up
            if zoom_mode_no_pinky[side] and span_delta is not None and abs(span_delta) >= self.ZOOM_START_DELTA:
                if not self.zoom_state_no_pinky[side]:
                    events.append(GestureEvent(type=GestureType.ZOOM_START_NO_PINKY, hand=side))
                    self.zoom_state_no_pinky[side] = True
            else:
                if self.zoom_state_no_pinky[side]:
                    if (not zoom_mode_no_pinky[side]) or (span_delta is None) or (abs(span_delta) <= self.ZOOM_END_DELTA):
                        events.append(GestureEvent(type=GestureType.ZOOM_END_NO_PINKY, hand=side))
                        self.zoom_state_no_pinky[side] = False

        # --------------------------
        # Events: swipe detection
        # Priority:
        # - only when exactly one hand visible
        # - only for open hand
        # - not during pinch
        # - not while hover posture is active
        # --------------------------
        if hand_count == 1:
            active_side = "left" if left_detected else "right"

            if open_hand[active_side] and not current_pinching[active_side] and not hover_posture[active_side]:
                swipe_event = self._detect_swipe(
                    hand=hands[active_side],
                    side=active_side,
                    current_time=current_time,
                )
                if swipe_event is not None and (current_time - self.last_swipe_time) > self.SWIPE_COOLDOWN:
                    events.append(swipe_event)
                    self.last_swipe_time = current_time
            else:
                self.hand_history[active_side].clear()
        else:
            self.hand_history["left"].clear()
            self.hand_history["right"].clear()

        signals = {
            "hand_count": hand_count,
            "left_detected": left_detected,
            "right_detected": right_detected,
            "pinching": current_pinching,
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

        # Update previous-frame memory
        for side in ("left", "right"):
            self.prev_index_up[side] = index_up[side]
            self.prev_middle_up[side] = middle_up[side]
            self.prev_hover_posture[side] = hover_posture[side]
            self.prev_pointer_position[side] = pointer_position[side]
            self.prev_thumb_index_distance[side] = thumb_index_distance[side]

        return {
            "hands": hands,
            "signals": signals,
            "events": events,
        }

    # ---------------------------------------
    # Helpers
    # ---------------------------------------

    def _count_true(self, values: List[bool]) -> int:
        return sum(1 for v in values if v)

    def _is_pinching(self, hand: HandData, was_pinching: bool) -> bool:
        """
        Pinch with hysteresis:
        - if already pinching, use looser END threshold to stay active
        - if not pinching, use stricter START threshold
        """
        distance = self._thumb_index_distance(hand)
        if distance is None:
            return False

        if was_pinching:
            return distance < self.PINCH_END_THRESHOLD
        return distance < self.PINCH_START_THRESHOLD

    def _thumb_index_distance(self, hand: HandData) -> Optional[float]:
        if hand.landmarks is None:
            return None

        thumb_tip = hand.landmarks[4]
        index_tip = hand.landmarks[8]

        dx = thumb_tip[0] - index_tip[0]
        dy = thumb_tip[1] - index_tip[1]

        return math.sqrt(dx * dx + dy * dy)

    def _is_finger_up(self, hand: HandData, tip_idx: int, pip_idx: int) -> bool:
        """
        Simple finger-up heuristic:
        smaller y means higher in the image.
        """
        if hand.landmarks is None:
            return False

        tip_y = hand.landmarks[tip_idx][1]
        pip_y = hand.landmarks[pip_idx][1]

        return tip_y < pip_y

    def _pointer_position(self, hand: HandData):
        """
        Pointer candidate:
        use index fingertip if available, else palm_center, else None.
        """
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

    def _detect_swipe(
        self,
        hand: HandData,
        side: str,
        current_time: float,
    ) -> Optional[GestureEvent]:
        if hand.landmarks is None or hand.palm_center is None:
            self.hand_history[side].clear()
            return None

        self.hand_history[side].append(
            {
                "time": current_time,
                "x": hand.palm_center[0],
                "y": hand.palm_center[1],
            }
        )

        self.hand_history[side] = [
            entry
            for entry in self.hand_history[side]
            if current_time - entry["time"] < self.SWIPE_TIME_WINDOW
        ]

        history = self.hand_history[side]
        if len(history) < self.MIN_SWIPE_SAMPLES:
            return None

        start_x = history[0]["x"]
        end_x = history[-1]["x"]
        delta_x = end_x - start_x

        start_y = history[0]["y"]
        end_y = history[-1]["y"]
        delta_y = end_y - start_y

        abs_dx = abs(delta_x)
        abs_dy = abs(delta_y)

        if abs_dx < self.SWIPE_THRESHOLD_X and abs_dy < self.SWIPE_THRESHOLD_Y:
            return None

        self.hand_history[side].clear()

        # Dominant-axis decision
        if abs_dx >= abs_dy:
            # Horizontal camera motion may feel mirrored in interaction space
            if delta_x < 0:
                return GestureEvent(type=GestureType.SWIPE_RIGHT, hand=side)
            return GestureEvent(type=GestureType.SWIPE_LEFT, hand=side)

        # In image coordinates, y grows downward
        if delta_y < 0:
            return GestureEvent(type=GestureType.SWIPE_UP, hand=side)
        return GestureEvent(type=GestureType.SWIPE_DOWN, hand=side)

# -----------------------------[ GestureDetector – Full Processing Spec ]-----------------------------------------------------
"""

----------------------------------------
1. Entry Point
----------------------------------------

def process_frame(frame) -> dict

Pipeline:
    frame
      ↓
    LandmarkDetector.extract_hands(frame)
      ↓
    hands (Dict[str, HandData])
      ↓
    process_hands(hands)
      ↓
    result dict returned

Frames are NOT stored. Only extracted features and small temporal memory are kept.

----------------------------------------
2. Internal Method
----------------------------------------

def process_hands(hands: Dict[str, HandData]) -> dict

This method:
- computes posture signals
- computes motion/deltas
- detects gesture transitions (events)
- updates internal memory
- returns final result

----------------------------------------
3. Return Structure
----------------------------------------

{
    "hands": {...},
    "signals": {...},
    "events": [...]
}

----------------------------------------
4. "hands" Field
----------------------------------------

Structure:
{
    "left": HandData(...),
    "right": HandData(...),
}

Meaning:
- Raw structured output from LandmarkDetector
- Contains:
    - landmarks
    - palm_center
    - bounding box
    - is_raised flag

Purpose:
- debugging
- future improvements
- raw geometry access

----------------------------------------
5. "signals" Field
----------------------------------------

Signals = continuous states (true NOW on this frame)

Structure:

{
    "hand_count": int,
    "left_detected": bool,
    "right_detected": bool,

    "pinching": {side: bool},

    "index_up": {side: bool},
    "middle_up": {side: bool},
    "ring_up": {side: bool},
    "pinky_up": {side: bool},

    "hover_posture": {side: bool},
    "open_hand": {side: bool},

    "both_hands_raised": bool,

    "pointer_position": {side: (x, y) or None},
    "pointer_delta": {side: (dx, dy) or None},

    "horizontal_delta": {side: dx or None},
    "vertical_delta": {side: dy or None},

    "thumb_index_distance": {side: float or None},
    "thumb_index_distance_delta": {side: float or None},

    "zoom_mode_pinky_up": {side: bool},
    "zoom_mode_no_pinky": {side: bool},
}

----------------------------------------
Signal Definitions
----------------------------------------

hand_count:
    Number of detected hands (0, 1, 2)

left_detected / right_detected:
    Whether each hand is visible

pinching:
    Whether thumb and index are close (state, not event)

index_up / middle_up / ring_up / pinky_up:
    Finger posture (tip_y < pip_y)

hover_posture:
    index_up AND middle_up

open_hand:
    At least 3 of {index, middle, ring, pinky} are up AND not pinching

both_hands_raised:
    Both hands marked as raised

pointer_position:
    Index fingertip position (fallback to palm center if needed)

pointer_delta:
    Movement since previous frame:
        (dx, dy) = (x_t - x_{t-1}, y_t - y_{t-1})

horizontal_delta / vertical_delta:
    Decomposed pointer movement

thumb_index_distance:
    Euclidean distance between thumb tip and index tip

thumb_index_distance_delta:
    Change in span since previous frame

zoom_mode_pinky_up:
    Valid zoom posture AND pinky_up == True

zoom_mode_no_pinky:
    Valid zoom posture AND pinky_up == False

----------------------------------------
6. "events" Field
----------------------------------------

Events = transitions detected ON THIS FRAME ONLY

Structure:

[
    GestureEvent(type=..., hand="left"/"right")
]

----------------------------------------
Event Types
----------------------------------------

Pinch:
    PINCH_START
    PINCH_END

Swipe (4 directions):
    SWIPE_LEFT
    SWIPE_RIGHT
    SWIPE_UP
    SWIPE_DOWN

Click:
    LEFT_CLICK
    RIGHT_CLICK

Scroll:
    SCROLL_START
    SCROLL_END

Zoom:
    ZOOM_START_PINKY_UP
    ZOOM_END_PINKY_UP
    ZOOM_START_NO_PINKY
    ZOOM_END_NO_PINKY

----------------------------------------
Event Meaning
----------------------------------------

Events represent transitions, not states.

Examples:
- PINCH_START → pinch became active
- LEFT_CLICK → index went down from hover posture
- SWIPE_LEFT → sufficient motion detected in window
- ZOOM_START → zoom regime entered

Events exist only for one frame.

----------------------------------------
7. Signals vs Events
----------------------------------------

Signals:
    "what is true right now"

Events:
    "what just happened"

Example:
    pinching = True  → signal
    PINCH_START      → event

----------------------------------------
8. Internal Memory (Temporal State)
----------------------------------------

The detector does NOT store frames.

It stores small temporal memory:

- previous pinch state
- previous hover posture
- previous finger states (index/middle)
- previous pointer position
- previous thumb-index distance
- swipe motion history (time window)
- scroll active state
- zoom active states

Purpose:
- compute deltas
- detect transitions
- stabilize gesture detection

----------------------------------------
9. Processing Pipeline (Conceptual)
----------------------------------------

For each frame:

1. Extract hands
2. Compute posture signals
3. Compute motion/deltas
4. Detect events (transitions)
5. Build signals dict
6. Update memory
7. Return result

----------------------------------------
10. Role in System Architecture
----------------------------------------

GestureDetector DOES NOT:
    - click UI elements
    - scroll widgets
    - manage app state

It ONLY:
    - interprets gestures
    - provides signals + events

Next layer (controller / state manager):
    - decides if a widget is hovered
    - applies click / scroll / drag
    - handles UI logic

----------------------------------------
11. One-Line Summary
----------------------------------------

GestureDetector returns:

    "what hands I see, what is true now, and what just happened"
"""