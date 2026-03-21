import cv2

from smartmirror.cv import (
    ClickGesture,
    GestureDetector,
    PinchGesture,
    ScrollGesture,
    SwipeGesture,
    ZoomGesture,
)


def main():
    # Current built-in gesture space:
    #
    # 1) PinchGesture
    #    - PINCH_START, PINCH_MOVE, PINCH_END
    #
    # 2) ClickGesture
    #    - LEFT_CLICK, RIGHT_CLICK
    #
    # 3) ScrollGesture
    #    - SCROLL_START, SCROLL_UPDATE, SCROLL_END
    #
    # 4) ZoomGesture (one-hand zoom with 2 modes)
    #    - ZOOM_START_PINKY_UP, ZOOM_UPDATE_PINKY_UP, ZOOM_END_PINKY_UP
    #    - ZOOM_START_NO_PINKY, ZOOM_UPDATE_NO_PINKY, ZOOM_END_NO_PINKY
    #
    # 5) SwipeGesture
    #    - SWIPE_LEFT, SWIPE_RIGHT, SWIPE_UP, SWIPE_DOWN
    #
    # You can customize this list per mode/page/widget by adding/removing gesture objects.
    gestures = [
        # PinchGesture(),
        # ClickGesture(),
        # ScrollGesture(),
        ZoomGesture(),
        SwipeGesture(),
    ]

    # debug=True opens an annotated camera window (bbox, trails, metrics, event feed)
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

            frame = cv2.flip(frame, 1)
            result = detector.process_frame(frame)

            # Events are transition or update signals detected on this frame.
            # For continuous gestures (PINCH_MOVE / SCROLL_UPDATE / ZOOM_UPDATE_*),
            # this may print many events while the interaction is active.
            if result["events"]:
                for event in result["events"]:
                    print(str(event))

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        detector.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
