from .base import BaseWidget

# Brush colours: the UI's palette plus a few that stand out on black.
DEFAULT_COLORS = ("#d5d5d5", "#fd7a33", "#ab32ac", "#3fd16b", "#3fa9f5", "#ffd23f")
# Brush sizes, in the canvas's chunky pixels, smallest first.
DEFAULT_SIZES = (1, 2, 4, 6)

# Open-hand sideways swipes step the brush size. The camera frame is mirrored, so a hand
# moving toward the right of the screen is a "swipe_left" (see PostureSwipeGesture).
SIZE_STEPS = {"swipe_left": 1, "swipe_right": -1}
CLEAR_GESTURES = ("swipe_up", "two_fingers_swipe_up")


class DrawingWidget(BaseWidget):
    """A canvas you draw on by pinching (thumb + index of the pointer hand).

    The strokes themselves never go through the backend: the frontend draws them from
    the `POINTER` messages (see docs/protocol.md). This widget holds the brush:
      - `left_click` (fold the index from the two-finger pose): next colour;
      - open hand swiped toward the screen's right / left: bigger / smaller brush;
      - a swipe up, open hand or two fingers (the page-change pose, so the natural one to try): clear.
    Pages change with two-finger swipes left/right, so none of these collide with them.
    Serialized as `data = {"color", "size", "clears"}`; `clears` counts the clears, so
    the frontend wipes its canvas whenever it changes.
    """

    type = "drawing"
    gestures = ("left_click", *SIZE_STEPS, *CLEAR_GESTURES)

    def __init__(self, colors=DEFAULT_COLORS, sizes=DEFAULT_SIZES, **kwargs):
        # A pinch is the pen here, so it must not also grab and drag the canvas.
        kwargs.setdefault("draggable", False)
        super().__init__(**kwargs)
        self.colors = list(colors)
        self.sizes = list(sizes)
        self._color = 0
        self._size = 0
        self._clears = 0
        self._update_data()

    def handle_gesture(self, event) -> bool:
        if event.name == "left_click":
            self._color = (self._color + 1) % len(self.colors)
        elif event.name in SIZE_STEPS:
            size = max(0, min(len(self.sizes) - 1, self._size + SIZE_STEPS[event.name]))
            if size == self._size:
                return False  # already the smallest / biggest
            self._size = size
        elif event.name in CLEAR_GESTURES:
            self._clears += 1
        else:
            return False
        self._update_data()
        return True

    def _update_data(self):
        self.data = {"color": self.colors[self._color], "size": self.sizes[self._size], "clears": self._clears}
