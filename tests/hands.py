"""Synthetic hands for camera-free tests."""

from smartmirror.vision import SIDES, HandData

_FINGERS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}


def make_hand(x=0.5, y=0.5, fingers_up=("index", "middle", "ring", "pinky"), pinch=False):
    """A hand centered on (x, y); `fingers_up` tips sit above their PIP joints."""
    landmarks = [(x, y, 0.0)] * 21
    landmarks[0] = (x, y + 0.2, 0.0)  # wrist
    for name, (tip, pip) in _FINGERS.items():
        landmarks[pip] = (x, y, 0.0)
        landmarks[tip] = (x, y - 0.1 if name in fingers_up else y + 0.05, 0.0)

    index_tip = landmarks[8]
    landmarks[4] = (index_tip[0] + (0.01 if pinch else 0.2), index_tip[1], 0.0)  # thumb tip

    xs = [point[0] for point in landmarks]
    ys = [point[1] for point in landmarks]
    return HandData(
        is_raised=landmarks[0][1] < 0.5,
        landmarks=landmarks,
        palm_center=(landmarks[9][0], landmarks[9][1]),
        bbox=(min(xs), min(ys), max(xs), max(ys)),
    )


def hands(left=None, right=None):
    detected = {"left": left, "right": right}
    return {side: detected[side] or HandData.empty() for side in SIDES}
