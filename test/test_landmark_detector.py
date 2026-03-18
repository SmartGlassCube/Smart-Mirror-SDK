import cv2
from smartmirror.cv import LandmarkDetector


def main():
    detector = LandmarkDetector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera")
        return

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Could not read frame")
        return

    hands = detector.extract_hands(frame)

    print("Left hand:")
    print(hands["left"])
    print()
    print("Right hand:")
    print(hands["right"])


if __name__ == "__main__":
    main()