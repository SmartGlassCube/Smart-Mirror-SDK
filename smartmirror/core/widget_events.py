import math

# Which widgets a default binding can target (`"target"` field in the bindings config).
WIDGET_TARGETS = {
    "any": lambda widget: True,
    "navigable": lambda widget: callable(getattr(widget, "apply_navigation", None)),
    "draggable": lambda widget: getattr(widget, "draggable", False),
    "none": None,  # handler doesn't need a resolved widget
}


class WidgetEventsMixin:
    """Gesture events aimed at widgets on the current page.

    1. Widgets that list the event in `gestures` get `handle_gesture(event)`.
    2. Otherwise the default bindings apply (`default_widget_event_bindings.json`):
       swipe/scroll navigation and pinch-to-drag.

    The target is the candidate nearest to `event.location` within
    `target_radius`, falling back to the page's first candidate.
    """

    def _dispatch_widget_event(self, event_name, event, now):
        widgets = self.get_current_widgets()

        listeners = [widget for widget in widgets if widget.handles(event_name)]
        listener = self._resolve_widget_for_event(event, listeners)
        if listener is not None and listener.handle_gesture(event):
            return True

        binding = self.widget_event_bindings.get(event_name)
        if binding is None:
            return False

        handler = getattr(self, binding.get("handler", "_handle_widget_navigation"), None)
        if not callable(handler):
            return False

        target = None
        can_target = WIDGET_TARGETS[binding.get("target", "navigable")]
        if can_target is not None:
            target = self._resolve_widget_for_event(event, [widget for widget in widgets if can_target(widget)])
            if target is None:
                return False

            cooldown_key = binding.get("cooldown_key")
            cooldown_config = binding.get("cooldown_config")
            if cooldown_key and cooldown_config and self._is_rate_limited(
                key=f"widget:{id(target)}:{cooldown_key}",
                now=now,
                cooldown=self.gesture_config.get(cooldown_config, 0.0),
            ):
                return False

        return bool(handler(widget=target, event=event, binding=binding))

    def _resolve_widget_for_event(self, event, candidates):
        if not candidates:
            return None

        location = getattr(event, "location", None)
        positioned = [
            widget for widget in candidates
            if widget.position.get("x") is not None and widget.position.get("y") is not None
        ]
        if location is None or not positioned:
            return candidates[0]

        nearest = min(positioned, key=lambda widget: _distance(widget, location))
        if _distance(nearest, location) <= self.gesture_config["target_radius"]:
            return nearest
        return candidates[0]

    def _handle_widget_navigation(self, widget, event, binding):
        horizontal_steps = int(binding.get("horizontal_steps", 0) or 0)
        vertical_steps = int(binding.get("vertical_steps", 0) or 0)
        if horizontal_steps == 0 and vertical_steps == 0:
            return False
        return widget.apply_navigation(horizontal_steps=horizontal_steps, vertical_steps=vertical_steps)

    def _handle_widget_scroll(self, widget, event, binding):
        velocity_y = (event.data or {}).get("velocity_y") or 0.0
        if abs(velocity_y) < self.gesture_config["scroll_velocity_threshold"]:
            return False
        return widget.apply_navigation(horizontal_steps=0, vertical_steps=1 if velocity_y > 0 else -1)

    def _handle_widget_drag_start(self, widget, event, binding):
        """Grab the targeted widget when a pinch begins."""
        if event.hand is None:
            return False
        self._dragging[event.hand] = widget
        widget.dragging = True
        return True

    def _handle_widget_drag_move(self, widget, event, binding):
        """Move the grabbed widget by the pinch delta (clamped to the screen)."""
        target = self._dragging.get(event.hand)
        if target is None:
            return False

        data = event.data or {}
        target.position["x"] = _clamp(target.position.get("x", 0.5) + data.get("dx", 0.0))
        target.position["y"] = _clamp(target.position.get("y", 0.5) + data.get("dy", 0.0))
        return True

    def _handle_widget_drag_end(self, widget, event, binding):
        """Release the grabbed widget when the pinch ends."""
        target = self._dragging.pop(event.hand, None)
        if target is None:
            return False
        target.dragging = False
        return True


def _distance(widget, location):
    return math.dist((widget.position["x"], widget.position["y"]), location)


def _clamp(value):
    return max(0.0, min(1.0, value))
