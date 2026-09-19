import json
import math
import time
from pathlib import Path


class StateManager:
    _JSON_CONFIG_DIR = Path(__file__).resolve().parent / "json_config"
    _DEFAULT_GESTURE_CONFIG_FILE = _JSON_CONFIG_DIR / "default_gesture_config.json"
    _DEFAULT_WIDGET_BINDINGS_FILE = _JSON_CONFIG_DIR / "default_widget_event_bindings.json"

    def __init__(
        self,
        graph=None,
        initial_node_id=None,
        gesture_config=None,
        event_bindings=None,
        widget_event_bindings=None,
        edge_gesture_fields=None,
    ):
        self.graph = graph or {"nodes": [], "edges": []}
        self.current_node_id = initial_node_id or self._get_default_node_id()
        self.gesture_config = self._load_json_config(file_path=self._DEFAULT_GESTURE_CONFIG_FILE)
        if gesture_config:
            self.gesture_config.update(gesture_config)

        self.event_bindings = event_bindings or {}
        self.widget_event_bindings = self._load_json_config(file_path=self._DEFAULT_WIDGET_BINDINGS_FILE)
        if widget_event_bindings:
            self.widget_event_bindings.update(widget_event_bindings)

        self.edge_gesture_fields = tuple(edge_gesture_fields or ("gesture", "trigger", "event"))
        self._last_event_times = {}
        self._dragging = {"left": None, "right": None}

    @classmethod
    def _load_json_config(cls, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as stream:
                loaded = json.load(stream)
        except OSError as error:
            raise FileNotFoundError(f"Required config file not found: {file_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in config file: {file_path}") from error

        if not isinstance(loaded, dict):
            raise ValueError(f"Config file must contain a JSON object: {file_path}")

        return loaded

    def _get_default_node_id(self):
        nodes = self.graph.get("nodes", [])
        if not nodes:
            return None
        return nodes[0].get("id")

    def set_graph(self, graph):
        self.graph = graph or {"nodes": [], "edges": []}
        if self.current_node_id is None:
            self.current_node_id = self._get_default_node_id()

    def set_current_node(self, node_id):
        self.current_node_id = node_id

    def get_current_node(self):
        for node in self.graph.get("nodes", []):
            if node.get("id") == self.current_node_id:
                return node
        return None

    def get_current_widgets(self):
        current_node = self.get_current_node()
        if not current_node:
            return []
        return current_node.get("widgets", [])

    def handle_gesture_events(self, events, signals=None, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        state_changed = False

        for event in events or []:
            event_name = event.type.value

            bound_changed = self._dispatch_bound_actions(event_name=event_name, event=event)
            state_changed = bound_changed or state_changed
            if bound_changed:
                continue

            navigated = self._dispatch_graph_navigation(event_name=event_name, now=now)
            state_changed = navigated or state_changed
            if navigated:
                continue

            widget_changed = self._dispatch_widget_event(event_name=event_name, event=event, now=now)
            state_changed = widget_changed or state_changed

        return state_changed

    def _dispatch_bound_actions(self, event_name, event):
        actions = self.event_bindings.get(event_name)
        if not actions:
            return False

        if not isinstance(actions, list):
            actions = [actions]

        changed = False
        for action in actions:
            changed = self._execute_action(action=action, event=event) or changed
        return changed

    def _execute_action(self, action, event):
        if callable(action):
            return bool(action(self, event))

        if isinstance(action, str):
            method = getattr(self, action, None)
            if callable(method):
                return bool(self._invoke_method(method=method, event=event, kwargs={}))
            return False

        if not isinstance(action, dict):
            return False

        target = action.get("target", "state_manager")
        method_name = action.get("method")
        kwargs = action.get("kwargs", {}) or {}
        if not method_name:
            return False

        if target == "state_manager":
            target_obj = self
        elif target == "current_widget":
            target_obj = self._resolve_widget_for_event(event)
        else:
            target_obj = getattr(self, target, None)

        if target_obj is None:
            return False

        method = getattr(target_obj, method_name, None)
        if not callable(method):
            return False

        return bool(self._invoke_method(method=method, event=event, kwargs=kwargs))

    def _invoke_method(self, method, event, kwargs):
        try:
            return method(event=event, **kwargs)
        except TypeError:
            try:
                return method(**kwargs)
            except TypeError:
                return method(event)

    def _dispatch_graph_navigation(self, event_name, now):
        if self._is_rate_limited(
            key=f"node:{event_name}",
            now=now,
            cooldown=self.gesture_config["node_navigation_cooldown"],
        ):
            return False
        return self._navigate_graph(event_name)

    def _dispatch_widget_event(self, event_name, event, now):
        binding = self.widget_event_bindings.get(event_name)
        if binding is None:
            return False

        target_widget = self._resolve_widget_for_event(event)
        if target_widget is None:
            return False

        cooldown_key = binding.get("cooldown_key")
        cooldown_config = binding.get("cooldown_config")
        if cooldown_key and cooldown_config:
            cooldown = self.gesture_config.get(cooldown_config, 0.0)
            if self._is_rate_limited(
                key=f"widget:{id(target_widget)}:{cooldown_key}",
                now=now,
                cooldown=cooldown,
            ):
                return False

        handler_name = binding.get("handler", "_handle_widget_navigation")
        handler = getattr(self, handler_name, None)
        if not callable(handler):
            return False

        return bool(handler(widget=target_widget, event=event, binding=binding))

    def _handle_widget_navigation(self, widget, event, binding):
        if not hasattr(widget, "apply_navigation"):
            return False

        horizontal_steps = int(binding.get("horizontal_steps", 0) or 0)
        vertical_steps = int(binding.get("vertical_steps", 0) or 0)
        if horizontal_steps == 0 and vertical_steps == 0:
            return False

        return bool(
            widget.apply_navigation(
                horizontal_steps=horizontal_steps,
                vertical_steps=vertical_steps,
            )
        )

    def _handle_widget_scroll(self, widget, event, binding):
        if not hasattr(widget, "apply_navigation"):
            return False

        data = getattr(event, "data", None) or {}
        velocity_y = data.get("velocity_y", 0.0)
        if abs(velocity_y) < self.gesture_config["scroll_velocity_threshold"]:
            return False

        vertical_steps = 1 if velocity_y > 0 else -1
        return bool(widget.apply_navigation(horizontal_steps=0, vertical_steps=vertical_steps))

    def _handle_widget_drag_start(self, widget, event, binding):
        """Lock onto the nearest widget when a pinch begins."""
        hand = getattr(event, "hand", None)
        if hand is None or widget is None:
            return False
        self._dragging[hand] = widget
        widget._is_dragging = True
        return True

    def _handle_widget_drag_move(self, widget, event, binding):
        """Move the dragged widget by the pinch delta."""
        hand = getattr(event, "hand", None)
        if hand is None:
            return False

        target = self._dragging.get(hand)
        if target is None:
            return False

        data = getattr(event, "data", None) or {}
        dx = data.get("dx", 0.0)
        dy = data.get("dy", 0.0)

        position = getattr(target, "position", None)
        if position is None:
            return False

        new_x = max(0.0, min(1.0, position.get("x", 0.5) + dx))
        new_y = max(0.0, min(1.0, position.get("y", 0.5) + dy))
        target.position["x"] = new_x
        target.position["y"] = new_y
        return True

    def _handle_widget_drag_end(self, widget, event, binding):
        """Release the dragged widget when the pinch ends."""
        hand = getattr(event, "hand", None)
        if hand is None:
            return False

        target = self._dragging.get(hand)
        if target is not None:
            target._is_dragging = False
        self._dragging[hand] = None
        return True

    def _resolve_widget_for_event(self, event):
        widgets = [
            widget
            for widget in self.get_current_widgets()
            if hasattr(widget, "apply_navigation")
        ]
        if not widgets:
            return None

        event_location = getattr(event, "location", None)
        if event_location is None:
            return widgets[0]

        best_widget = None
        best_distance = float("inf")
        for widget in widgets:
            position = getattr(widget, "position", {}) or {}
            x = position.get("x")
            y = position.get("y")
            if x is None or y is None:
                continue
            distance = math.dist((x, y), event_location)
            if distance < best_distance:
                best_distance = distance
                best_widget = widget

        if best_widget is None:
            return widgets[0]

        if best_distance <= self.gesture_config["target_radius"]:
            return best_widget
        return widgets[0]

    def _navigate_graph(self, gesture_name):
        current_node_id = self.current_node_id
        if current_node_id is None:
            return False

        edges = self.graph.get("edges", [])
        matching_edges = [
            edge
            for edge in edges
            if edge.get("from") == current_node_id or edge.get("source") == current_node_id
        ]
        if not matching_edges:
            return False

        matched = [
            edge
            for edge in matching_edges
            if any(edge.get(field) == gesture_name for field in self.edge_gesture_fields)
        ]

        chosen_edge = None
        if matched:
            chosen_edge = matched[0]
        elif self.gesture_config.get("allow_unmatched_single_edge_navigation", False) and len(matching_edges) == 1:
            chosen_edge = matching_edges[0]

        if chosen_edge is None:
            return False

        next_node_id = chosen_edge.get("to") or chosen_edge.get("target")
        if next_node_id is None or next_node_id == self.current_node_id:
            return False

        if self._find_node(next_node_id) is None:
            return False

        self.current_node_id = next_node_id
        return True

    def _find_node(self, node_id):
        for node in self.graph.get("nodes", []):
            if node.get("id") == node_id:
                return node
        return None

    def _is_rate_limited(self, key, now, cooldown):
        if cooldown is None or cooldown <= 0:
            return False
        previous = self._last_event_times.get(key)
        if previous is not None and (now - previous) < cooldown:
            return True
        self._last_event_times[key] = now
        return False

    def get_state_snapshot(self):
        current_node = self.get_current_node() or {"id": None, "widgets": []}
        widgets = current_node.get("widgets", [])
        nodes = self.graph.get("nodes", [])

        return {
            "nodeId": current_node.get("id"),
            "widgets": [widget.serialize() for widget in widgets],
            "nodes": [
                {
                    "id": node.get("id"),
                    "widgets": [widget.serialize() for widget in node.get("widgets", [])],
                }
                for node in nodes
            ],
        }
