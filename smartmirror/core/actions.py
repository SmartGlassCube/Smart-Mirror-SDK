from .callables import call_flexibly


class ActionBindingsMixin:
    """App-level `event_bindings`: run user-defined actions for a gesture event.

    An action is one of:
      - a callable `action(state_manager, event)`;
      - the name of a `StateManager` method;
      - `{"target": "state_manager" | "current_widget" | <attribute>, "method": str, "kwargs": dict}`.
    """

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
            action = {"method": action}
        if not isinstance(action, dict) or not action.get("method"):
            return False

        target = action.get("target", "state_manager")
        if target == "state_manager":
            target_obj = self
        elif target == "current_widget":
            target_obj = self._resolve_widget_for_event(event, self.get_current_widgets())
        else:
            target_obj = getattr(self, target, None)

        method = getattr(target_obj, action["method"], None)
        if not callable(method):
            return False

        kwargs = action.get("kwargs") or {}
        return bool(call_flexibly(method, ((), {"event": event, **kwargs}), ((), kwargs), ((event,), kwargs)))
