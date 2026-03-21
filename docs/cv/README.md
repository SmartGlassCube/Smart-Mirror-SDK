# CV Module

This module detects hand-based gestures from camera frames.

## Main flow

1. `landmark_detector.py` extracts left/right `HandData`.
2. `gesture_detector.py` builds shared per-frame `signals`.
3. A list of gesture objects (`Gesture` subclasses) runs `detect(context)`.
4. The detector returns:
   - `hands`
   - `signals`
   - `events`

## Current gesture files

- `smartmirror/cv/gestures/pinch.py`
- `smartmirror/cv/gestures/click.py`
- `smartmirror/cv/gestures/scroll.py`
- `smartmirror/cv/gestures/zoom.py`
- `smartmirror/cv/gestures/swipe.py`
- `smartmirror/cv/gestures/two_fingers_swipe.py`

## Two-fingers node navigation

`TwoFingersSwipeGesture` emits:

- `TWO_FINGERS_SWIPE_LEFT`
- `TWO_FINGERS_SWIPE_RIGHT`
- `TWO_FINGERS_SWIPE_UP`
- `TWO_FINGERS_SWIPE_DOWN`

Detection conditions:

- exactly one hand detected
- index + middle fingers up (`hover_posture`) and not pinching
- palm-pointer movement crosses swipe threshold

Use these events in graph edges via `gesture` or `trigger` fields.

## How to add a new gesture smoothly

1. Create one new file in `smartmirror/cv/gestures/`.
   - Example: `smartmirror/cv/gestures/hold.py`

2. Implement a class that inherits from `Gesture` (or `DynamicGesture` if it needs multi-frame memory).
   - Use this signature:
     - `detect(self, context: GestureContext) -> List[GestureEvent]`

3. Read inputs from `context` only.
   - `context.hands` for raw hand data.
   - `context.signals` for normalized/common signals.
   - `context.timestamp` for time-based logic.

4. Keep internal state inside the gesture class.
   - Use instance variables to track previous frame values.
   - Emit transition events (`START`, `END`) and update events (`*_UPDATE`) when needed.

5. Add any new event names to `smartmirror/cv/gesture_types.py`.
   - Add entries in `GestureType`.
   - Return `GestureEvent(type=..., hand=..., location=..., data=...)` from your gesture.

6. Export the new gesture in `smartmirror/cv/gestures/__init__.py`.

7. Add it to `smartmirror/cv/gestures/default_set.py` if it should be part of defaults.
   - Otherwise instantiate it only where needed (page/widget/profile-specific lists).

8. Test quickly with `examples/gesture_detector_debug.py`.
   - Run with `debug=True` to inspect overlay and emitted events.

## Design rules

- One gesture per file.
- Keep `gesture_detector.py` as orchestrator only.
- Put gesture-specific logic and memory in gesture classes.
- Prefer using shared `signals` before recalculating geometry inside each gesture.
- Emit compact events with useful metadata in `data` for downstream UI/state logic.
