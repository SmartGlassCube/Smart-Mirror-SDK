import cv2
from smartmirror.cv import GestureDetector


def main():
    detector = GestureDetector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera")
        return

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Could not read frame")
        return

    result = detector.process_frame(frame)
    print(result)


if __name__ == "__main__":
    main()