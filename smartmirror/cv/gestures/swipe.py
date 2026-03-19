from collections import deque
from gestures.base import DynamicGesture


class Swipe(DynamicGesture):
    """
    Tracks right hand index finger tip over multiple frames
    Detects: swipe_left, swipe_right, swipe_up, swipe_down
    """

    def __init__(self, history_length=15, threshold=0.15):
        self.history       = deque(maxlen=history_length)
        self.threshold     = threshold

    def update(self, hands):
        """
        Call every frame passing full HandsData
        Returns: "swipe_left", "swipe_right", "swipe_up", "swipe_down" or None
        """
        # use right hand index finger tip
        if hands.right[8] is None:
            self.history.clear()
            return None

        x, y, _ = hands.right[8]
        self.history.append((x, y))

        if len(self.history) < self.history.maxlen:
            return None

        x_start, y_start = self.history[0]
        x_end,   y_end   = self.history[-1]

        dx = x_end - x_start  # positive = moved right
        dy = y_end - y_start  # positive = moved down

        if abs(dx) < self.threshold and abs(dy) < self.threshold:
            return None

        # dominant axis wins
        if abs(dx) > abs(dy):
            result = "swipe_right" if dx > 0 else "swipe_left"
        else:
            result = "swipe_down" if dy > 0 else "swipe_up"

        self.history.clear()  # reset after detecting
        return result