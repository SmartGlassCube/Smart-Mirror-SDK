import itertools
from typing import Any, Callable, Dict, Iterable, Optional

_ids = itertools.count(1)


class BaseWidget:
    """Python model of one mirror widget, serialized to the frontend on every state update.

    To add a widget type, subclass and set `type` to the key the frontend
    widget registry uses (`frontend/src/widgets/<type>/index.ts`):

        class ClockWidget(BaseWidget):
            type = "clock"

    Optional hooks:
      - `gestures` + `handle_gesture(event)`: react to specific gesture events.
      - `apply_navigation(horizontal_steps, vertical_steps)`: opt into the
        default swipe/scroll navigation bindings.
      - `serialize()`: add fields for the frontend.
    """

    type = "widget"
    refresh_interval = 300  # seconds between `data_provider` calls
    gestures: Iterable[str] = ()  # event names routed to `handle_gesture`

    def __init__(
        self,
        position: Optional[Dict[str, float]] = None,
        content: Any = None,
        data: Any = None,
        data_provider: Optional[Callable] = None,
        refresh_interval: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        gestures: Optional[Iterable[str]] = None,
        draggable: bool = True,
        widget_id: Optional[str] = None,
        widget_type: Optional[str] = None,
    ):
        if widget_type is not None:
            self.type = widget_type
        if refresh_interval is not None:
            self.refresh_interval = refresh_interval
        if gestures is not None:
            self.gestures = gestures
        self.gestures = frozenset(self.gestures)

        self.id = widget_id or f"{self.type}-{next(_ids)}"
        self.position = dict(position or {})  # {"x": 0..1, "y": 0..1}, fraction of the screen
        self.content = content
        self.data = data
        self.data_provider = data_provider
        self.metadata = dict(metadata or {})
        self.draggable = draggable
        self.dragging = False
        self._last_data_update = 0.0

    def handles(self, event_name: str) -> bool:
        return event_name in self.gestures

    def handle_gesture(self, event) -> bool:
        """Called for events listed in `gestures` that target this widget. Return True if it changed."""
        return False

    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "position": self.position,
            "content": self.content,
            "data": self.data,
            "metadata": self.metadata,
            "dragging": self.dragging,
        }
