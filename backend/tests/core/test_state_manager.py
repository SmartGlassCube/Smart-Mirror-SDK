import pytest

from glasscube.core import StateManager
from glasscube.vision import GestureEvent, GestureType
from glasscube.widgets import BaseWidget, CalendarWidget, TextWidget


def event(name, location=None, hand="right", data=None):
    return GestureEvent(type=name, hand=hand, location=location, data=data)


def two_page_graph(**edge):
    return {
        "nodes": [{"id": "home", "widgets": []}, {"id": "focus", "widgets": []}],
        "edges": [{"from": "home", "to": "focus", "gesture": "two_fingers_swipe_left", **edge}],
    }


def test_edge_navigation_accepts_enum_and_string_events():
    state = StateManager(graph=two_page_graph())

    assert state.handle_gesture_events([GestureEvent(type=GestureType.TWO_FINGERS_SWIPE_LEFT)], timestamp=0)
    assert state.current_node_id == "focus"
    assert not state.handle_gesture_events([event("two_fingers_swipe_left")], timestamp=1)


def test_edge_aliases_and_cooldown():
    graph = {
        "nodes": [{"id": "a", "widgets": []}, {"id": "b", "widgets": []}],
        "edges": [
            {"source": "a", "target": "b", "trigger": "thumbs_up"},
            {"source": "b", "target": "a", "trigger": "thumbs_up"},
        ],
    }
    state = StateManager(graph=graph, gesture_config={"node_navigation_cooldown": 0.8})

    assert state.handle_gesture_events([event("thumbs_up")], timestamp=0.0)
    assert not state.handle_gesture_events([event("thumbs_up")], timestamp=0.5)  # cooling down
    assert state.handle_gesture_events([event("thumbs_up")], timestamp=1.0)
    assert state.current_node_id == "a"


def test_event_binding_can_switch_page():
    state = StateManager(
        graph=two_page_graph(),
        event_bindings={"left_click": {"method": "set_current_node", "kwargs": {"node_id": "focus"}}},
    )

    assert state.handle_gesture_events([event("left_click")], timestamp=0)
    assert state.current_node_id == "focus"


def test_swipe_and_scroll_navigate_text_widget():
    text = TextWidget(position={"x": 0.5, "y": 0.5}, content={"a": ["a1", "a2"], "b": ["b1"]})
    state = StateManager(graph={"nodes": [{"id": "home", "widgets": [text]}], "edges": []})

    assert state.handle_gesture_events([event("swipe_left", (0.5, 0.5))], timestamp=0)
    assert text.content == "a2"
    assert state.handle_gesture_events([event("scroll_start", data={"velocity_y": 0.1})], timestamp=1)
    assert text.content == "b1"


def test_pinch_drags_the_nearest_widget_of_any_type():
    text = TextWidget(position={"x": 0.2, "y": 0.2}, content="hello")
    calendar = CalendarWidget(position={"x": 0.8, "y": 0.8})
    state = StateManager(graph={"nodes": [{"id": "home", "widgets": [text, calendar]}], "edges": []})

    assert state.handle_gesture_events([event("pinch_start", (0.78, 0.8))], timestamp=0)
    assert calendar.dragging and not text.dragging

    state.handle_gesture_events([event("pinch_move", (0.7, 0.8), data={"dx": -0.1, "dy": 0.5})], timestamp=0.1)
    assert calendar.position == pytest.approx({"x": 0.7, "y": 1.0})  # y clamped to the screen

    assert state.handle_gesture_events([event("pinch_end")], timestamp=0.2)
    assert not calendar.dragging
    assert state.get_state_snapshot()["widgets"][1]["position"] == calendar.position


def test_non_draggable_widget_is_not_grabbed():
    pinned = CalendarWidget(position={"x": 0.5, "y": 0.5}, draggable=False)
    state = StateManager(graph={"nodes": [{"id": "home", "widgets": [pinned]}], "edges": []})

    assert not state.handle_gesture_events([event("pinch_start", (0.5, 0.5))], timestamp=0)


class CounterWidget(BaseWidget):
    type = "counter"
    gestures = ("left_click", "swipe_left")

    def __init__(self, **kwargs):
        super().__init__(content="0", **kwargs)

    def handle_gesture(self, event):
        if event.name != "left_click":
            return False  # fall through to the default bindings
        self.content = str(int(self.content) + 1)
        return True


def test_custom_widget_handles_its_gestures():
    counter = CounterWidget(position={"x": 0.5, "y": 0.5})
    text = TextWidget(position={"x": 0.1, "y": 0.1}, content=["one", "two"])
    state = StateManager(graph={"nodes": [{"id": "home", "widgets": [counter, text]}], "edges": []})

    assert state.handle_gesture_events([event("left_click", (0.5, 0.5))], timestamp=0)
    assert counter.content == "1"

    # Unhandled by the widget -> default swipe binding still navigates the text widget.
    assert state.handle_gesture_events([event("swipe_left", (0.5, 0.5))], timestamp=1)
    assert text.content == "two"

    snapshot = state.get_state_snapshot()
    assert snapshot["nodeId"] == "home" and snapshot["nodeIds"] == ["home"]
    assert [w["type"] for w in snapshot["widgets"]] == ["counter", "text"]


def test_unknown_binding_target_is_rejected():
    with pytest.raises(ValueError, match="unknown target"):
        StateManager(widget_event_bindings={"fist": {"handler": "_handle_widget_navigation", "target": "nope"}})
