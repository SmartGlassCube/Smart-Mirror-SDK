from .base import BaseWidget

# Brush colours: the UI's palette plus a few that stand out on black.
DEFAULT_COLORS = ("#d5d5d5", "#fd7a33", "#ab32ac", "#3fd16b", "#3fa9f5", "#ffd23f")
# Brush sizes, in the canvas's chunky pixels.
DEFAULT_SIZES = (1, 2, 4)


class DrawingWidget(BaseWidget):
    """A canvas you draw on by pinching (thumb + index of the pointer hand).

    The strokes themselves never go through the backend: the frontend draws them from
    the `POINTER` messages (see docs/protocol.md). This widget holds the brush:
      - `left_click`: next colour, `right_click`: next brush size,
      - a swipe up, open hand or two fingers (the page-change pose, so the natural one to try): clear.
    Serialized as `data = {"color", "size", "clears"}`; `clears` counts the clears, so
    the frontend wipes its canvas whenever it changes.
    """

    type = "drawing"
    gestures = ("left_click", "right_click", "swipe_up", "two_fingers_swipe_up")

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
        elif event.name == "right_click":
            self._size = (self._size + 1) % len(self.sizes)
        elif event.name in ("swipe_up", "two_fingers_swipe_up"):
            self._clears += 1
        else:
            return False
        self._update_data()
        return True

    def _update_data(self):
        self.data = {"color": self.colors[self._color], "size": self.sizes[self._size], "clears": self._clears}
