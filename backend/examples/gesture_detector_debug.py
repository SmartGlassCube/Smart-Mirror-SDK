"""Standalone gesture debugging: annotated camera window + event log. Press q to quit."""

import cv2

from glasscube.vision import (
    ClickGesture,
    GestureDetector,
    PinchGesture,
    ScrollGesture,
    SwipeGesture,
    TwoFingersSwipeGesture,
    ZoomGesture,
)


def main():
    # Pick the gestures to debug (or `default_gesture_set()` for all of them).
    # Custom `Gesture` subclasses can be added to this list too.
    gestures = [
        PinchGesture(),  # pinch_start / pinch_move / pinch_end
        ClickGesture(),  # left_click / right_click
        ScrollGesture(),  # scroll_start / scroll_update / scroll_end
        ZoomGesture(),  # zoom_{start,update,end}_{pinky_up,no_pinky}
        SwipeGesture(),  # swipe_{left,right,up,down}
        TwoFingersSwipeGesture(),  # two_fingers_swipe_{left,right,up,down}
    ]
    detector = GestureDetector(gestures=gestures, debug=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera")
        return

    print("Running gesture detector in debug mode. Press q to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read frame")
                break

            # Continuous gestures (pinch_move, scroll_update, zoom_update_*) print every frame while active.
            for event in detector.process_frame(cv2.flip(frame, 1))["events"]:
                print(event)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        detector.close()


if __name__ == "__main__":
    main()
