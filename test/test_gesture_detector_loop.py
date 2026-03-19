import cv2
from smartmirror.cv import GestureDetector


def main():
    detector = GestureDetector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera")
        return

    print("Press q to quit")

    for _ in range(1000):  # Limit to 1000 frames for testing
        ret, frame = cap.read()
        if not ret:
            print("Could not read frame")
            break

        result = detector.process_frame(frame)

        print("signals:", result["signals"])
        if result["events"]:
            print("events:", result["events"])

        cv2.imshow("Gesture Test", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()