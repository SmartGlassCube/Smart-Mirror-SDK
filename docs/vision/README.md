# Vision Module

`smartmirror/vision` turns camera frames into gesture events.

## Main flow

1. `landmark_detector.py`: MediaPipe extracts left/right `HandData`. A missing hand is `HandData.empty()`. The model file is downloaded on first use.
2. `gesture_detector.py`: builds the shared per-frame `signals` once, then runs every configured `Gesture`.
3. Each gesture's `detect(context)` returns a list of `GestureEvent(type, hand, location, data)`.
4. `process_frame(frame)` returns `{"hands", "signals", "events"}`. Use `process_hands(hands, timestamp=...)` to feed hands from another source, such as a recording or a test.
5. `debug_overlay.py`: with `GestureDetector(debug=True)`, draws an annotated window (boxes, trails, metrics, event feed).

`GestureEvent.type` is either a `GestureType` (built-ins) or a plain string (custom gestures). `event.name` always gives the string used by bindings and graph edges.

## Built-in gestures

| Gesture | Base | Events |
|---|---|---|
| `PinchGesture` | `Gesture` | `pinch_start`, `pinch_move` (`data: dx, dy`), `pinch_end` |
| `ClickGesture` | `Gesture` | `left_click`, `right_click` |
| `ScrollGesture` | `ContinuousGesture` | `scroll_start/update/end` (`data: velocity_y`) |
| `ZoomGesture` | `ContinuousGesture` | `zoom_{start,update,end}_{pinky_up,no_pinky}` (`data: span_delta`) |
| `SwipeGesture` | `PostureSwipeGesture` | `swipe_{left,right,up,down}` (open hand) |
| `TwoFingersSwipeGesture` | `PostureSwipeGesture` | `two_fingers_swipe_{left,right,up,down}` (only index + middle up) |

Swipes need exactly one hand in the frame. Because the frame is mirrored, moving your hand toward screen-left produces `*_swipe_right`.

## Signals

Every value except the presence flags is a per-side dict: `signals[name]["left" | "right"]`.

| Signal | Meaning |
|---|---|
| `hand_count`, `left_detected`, `right_detected` | Presence |
| `pinching` | Thumb–index span, with hysteresis: starts below 0.045, ends above 0.065 |
| `index_up`, `middle_up`, `ring_up`, `pinky_up` | Fingertip is above its PIP joint |
| `hover_posture` | Index and middle fingers up |
| `open_hand` | At least 3 of the 4 fingers up and not pinching |
| `pointer_position` | Index fingertip (falls back to palm center) |
| `pointer_delta`, `horizontal_delta`, `vertical_delta` | Frame-to-frame pointer movement |
| `thumb_index_distance`, `thumb_index_distance_delta` | Pinch/zoom span |
| `zoom_mode_pinky_up`, `zoom_mode_no_pinky` | Span ≥ 0.08, not pinching, with the pinky up / down |
| `both_hands_raised` | Both wrists in the upper half of the frame (not per-side) |

Thresholds are constructor arguments: `GestureDetector(pinch_start_threshold=..., pinch_end_threshold=..., zoom_min_span=...)`.

## Adding a gesture

See [Extending the SDK → Add a gesture](../extending.md#1-add-a-gesture). In short:

1. Subclass `Gesture` (or `ContinuousGesture` / `PostureSwipeGesture`) in your own code. One gesture per class, with its memory kept in instance attributes.
2. Return `GestureEvent(type="your_event", hand=..., location=..., data=...)`. You don't need to edit the enum.
3. Pass it in: `GestureDetector(gestures=default_gesture_set() + [YourGesture()])`.
4. Check it with `examples/gesture_detector_debug.py`.

To contribute a gesture to the SDK itself, also add its event names to `GestureType`, export it in `gestures/__init__.py`, and (optionally) add it to `default_gesture_set()`.

## Design rules

- `gesture_detector.py` only orchestrates: it builds signals and runs gestures. Drawing lives in `debug_overlay.py`.
- Put gesture-specific logic and memory in the gesture class.
- Prefer the shared `signals` over recomputing geometry inside a gesture.
- Emit compact events, with the useful numbers in `data`.
