import time

from ..config import DEFAULT_GESTURE_CONFIG_FILE, DEFAULT_WIDGET_BINDINGS_FILE, load_json_config
from .actions import ActionBindingsMixin
from .navigation import PageNavigationMixin
from .widget_events import WIDGET_TARGETS, WidgetEventsMixin


class StateManager(ActionBindingsMixin, PageNavigationMixin, WidgetEventsMixin):
    """Turns gesture events into state changes (current page, widget content/position).

    Each event goes through these stages, stopping at the first that changes state:
      1. `event_bindings`: app-level custom actions (see `ActionBindingsMixin`);
      2. page graph edges (see `PageNavigationMixin`);
      3. widget events (see `WidgetEventsMixin`).
    """

    def __init__(
        self,
        graph=None,
        initial_node_id=None,
        gesture_config=None,
        event_bindings=None,
        widget_event_bindings=None,
        edge_gesture_fields=("gesture", "trigger", "event"),
    ):
        self.gesture_config = {**load_json_config(DEFAULT_GESTURE_CONFIG_FILE), **(gesture_config or {})}
        self.widget_event_bindings = {
            **load_json_config(DEFAULT_WIDGET_BINDINGS_FILE),
            **(widget_event_bindings or {}),
        }
        self._validate_widget_bindings()
        self.event_bindings = event_bindings or {}
        self.edge_gesture_fields = tuple(edge_gesture_fields)

        self._last_event_times = {}
        self._dragging = {}  # hand -> widget being dragged

        self.current_node_id = initial_node_id
        self.set_graph(graph)

    def handle_gesture_events(self, events, signals=None, timestamp=None):
        """Apply a frame's events. Returns True if the state changed and should be broadcast."""
        now = time.time() if timestamp is None else timestamp
        state_changed = False

        for event in events or []:
            event_name = event.name
            state_changed = (
                self._dispatch_bound_actions(event_name=event_name, event=event)
                or self._dispatch_graph_navigation(event_name=event_name, now=now)
                or self._dispatch_widget_event(event_name=event_name, event=event, now=now)
                or state_changed
            )

        return state_changed

    def get_state_snapshot(self):
        """State sent to the frontend: the active page's widgets plus the list of page ids."""
        return {
            "nodeId": self.current_node_id,
            "nodeIds": [node.get("id") for node in self.graph.get("nodes", [])],
            "widgets": [widget.serialize() for widget in self.get_current_widgets()],
        }

    def _is_rate_limited(self, key, now, cooldown):
        if cooldown is None or cooldown <= 0:
            return False
        previous = self._last_event_times.get(key)
        if previous is not None and (now - previous) < cooldown:
            return True
        self._last_event_times[key] = now
        return False

    def _validate_widget_bindings(self):
        for event_name, binding in self.widget_event_bindings.items():
            target = binding.get("target", "navigable")
            if target not in WIDGET_TARGETS:
                raise ValueError(
                    f"Widget binding {event_name!r}: unknown target {target!r} "
                    f"(expected one of {sorted(WIDGET_TARGETS)})"
                )
