import cv2
from hand_data import HandsData
from gestures import Fist, OpenHand, ThumbsUp, ThumbsDown, Swipe

hands = HandsData()
cap   = cv2.VideoCapture(0)

# static gestures
static_gestures = {
    "Fist":        Fist(),
    "Open Hand":   OpenHand(),
    "Thumbs Up":   ThumbsUp(),
    "Thumbs Down": ThumbsDown(),
}

# dynamic gesture
swipe = Swipe(history_length=15, threshold=0.15)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    hands.update(frame)

    # check static gestures on right hand
    if hands.right[0] is not None:
        for name, gesture in static_gestures.items():
            if gesture.detect(hands.right):
                print(f"Static: {name}")

    # check swipe — passes full HandsData
    result = swipe.update(hands)
    if result:
        print(f"Dynamic: {result}")

    cv2.imshow("Hands Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
hands.close()
cv2.destroyAllWindows()