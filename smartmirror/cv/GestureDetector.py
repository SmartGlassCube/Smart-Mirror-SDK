import cv2
import math
from hand_data import HandsData
from gestures import Fist, OpenHand, ThumbsUp, ThumbsDown, Swipe

hands = HandsData()
cap   = cv2.VideoCapture(0)

static_gestures = {
    "Fist":        Fist(),
    "Open Hand":   OpenHand(),
    "Thumbs Up":   ThumbsUp(),
    "Thumbs Down": ThumbsDown(),
}

swipe = Swipe(history_length=15, threshold=0.10)

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]


def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


def draw_landmarks(frame, hand):
    if hand[0] is None:
        return
    h, w, _ = frame.shape

    for start, end in HAND_CONNECTIONS:
        if hand[start] and hand[end]:
            x1, y1 = int(hand[start][0] * w), int(hand[start][1] * h)
            x2, y2 = int(hand[end][0] * w),   int(hand[end][1] * h)
            cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)

    for lm in hand:
        if lm is None:
            continue
        x, y = int(lm[0] * w), int(lm[1] * h)
        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
        cv2.circle(frame, (x, y), 5, (0, 0, 0),   1)


def debug_distances(hand):
    if hand[0] is None:
        return
    wrist    = hand[0]
    mcp_dist = dist(wrist, hand[5])
    if mcp_dist == 0:
        return
    print(f"Index:  {dist(wrist, hand[8])  / mcp_dist:.3f}")
    print(f"Middle: {dist(wrist, hand[12]) / mcp_dist:.3f}")
    print(f"Ring:   {dist(wrist, hand[16]) / mcp_dist:.3f}")
    print(f"Pinky:  {dist(wrist, hand[20]) / mcp_dist:.3f}")
    print(f"Thumb gap (CMC-tip): {hand[2][1] - hand[4][1]:.3f}")
    print("---")


while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    hands.update(frame)

    draw_landmarks(frame, hands.left)
    draw_landmarks(frame, hands.right)

    if hands.left[0] is not None:
        debug_distances(hands.left)

        for name, gesture in static_gestures.items():
            if gesture.detect(hands.left):
                cv2.putText(frame, f"Left: {name}", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    result = swipe.update(hands)
    if result:
        cv2.putText(frame, f"Right: {result}", (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("Hands Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
hands.close()
cv2.destroyAllWindows()