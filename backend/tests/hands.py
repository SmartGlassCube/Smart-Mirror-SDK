"""Synthetic hands for camera-free tests."""

from glasscube.vision import SIDES, HandData

# finger -> (x offset, MCP, PIP, DIP, TIP landmark indices)
_FINGERS = {
    "index": (-0.03, 5, 6, 7, 8),
    "middle": (0.0, 9, 10, 11, 12),
    "ring": (0.03, 13, 14, 15, 16),
    "pinky": (0.06, 17, 18, 19, 20),
}


def make_hand(x=0.5, y=0.5, fingers_up=("index", "middle", "ring", "pinky"), pinch=False):
    """A plausible upright hand; its middle-finger PIP joint sits at (x, y).

    Fingers in `fingers_up` point up (tip above PIP); the others curl down.
    With `pinch`, the thumb tip touches the index tip.
    """
    landmarks = [(x, y, 0.0)] * 21
    landmarks[0] = (x, y + 0.2, 0.0)  # wrist
    for name, (dx, mcp, pip, dip, tip) in _FINGERS.items():
        fx = x + dx
        landmarks[mcp] = (fx, y + 0.07, 0.0)
        landmarks[pip] = (fx, y, 0.0)
        up = name in fingers_up
        landmarks[dip] = (fx, y - 0.05 if up else y + 0.03, 0.0)
        landmarks[tip] = (fx, y - 0.1 if up else y + 0.05, 0.0)

    index_tip = landmarks[8]
    thumb_tip = (index_tip[0] - 0.01, index_tip[1], 0.0) if pinch else (index_tip[0] - 0.2, index_tip[1] + 0.1, 0.0)
    landmarks[1] = (x - 0.06, y + 0.16, 0.0)
    landmarks[2] = (x - 0.09, y + 0.12, 0.0)
    landmarks[3] = ((landmarks[2][0] + thumb_tip[0]) / 2, (landmarks[2][1] + thumb_tip[1]) / 2, 0.0)
    landmarks[4] = thumb_tip

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
