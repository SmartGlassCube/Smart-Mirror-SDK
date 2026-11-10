from smartmirror.app.pages import build_graph
from smartmirror.app.settings import Settings
from smartmirror.core import StateManager
from smartmirror.vision import GestureEvent
from smartmirror.widgets import DrawingWidget


def event(name):
    return GestureEvent(type=name, hand="right", location=(0.5, 0.5), data={"dx": 0.1, "dy": 0.1})


def drawing_page(widget):
    return StateManager(graph={"nodes": [{"id": "draw", "widgets": [widget]}], "edges": []})


def test_clicks_change_the_brush_and_swipe_up_clears():
    drawing = DrawingWidget(colors=["red", "blue"], sizes=[1, 3])
    state = drawing_page(drawing)
    assert drawing.data == {"color": "red", "size": 1, "clears": 0}

    assert state.handle_gesture_events([event("left_click")], timestamp=0)
    assert state.handle_gesture_events([event("right_click")], timestamp=1)
    assert state.handle_gesture_events([event("swipe_up")], timestamp=2)
    assert drawing.data == {"color": "blue", "size": 3, "clears": 1}
    assert state.get_state_snapshot()["widgets"][0]["data"] == drawing.data

    state.handle_gesture_events([event("left_click")], timestamp=3)
    assert drawing.data["color"] == "red"  # wraps around
    assert state.handle_gesture_events([event("two_fingers_swipe_up")], timestamp=4)
    assert drawing.data["clears"] == 2  # the page-change pose clears too


def test_pinching_draws_instead_of_dragging_the_canvas():
    drawing = DrawingWidget(position={"x": 0.5, "y": 0.5})
    state = drawing_page(drawing)

    for name in ("pinch_start", "pinch_move", "pinch_end"):
        assert not state.handle_gesture_events([event(name)], timestamp=0)
    assert drawing.position == {"x": 0.5, "y": 0.5}
    assert not drawing.dragging


def test_the_draw_page_sits_past_games():
    state = StateManager(graph=build_graph(Settings(), None), initial_node_id="games")

    state.handle_gesture_events([event("two_fingers_swipe_right")], timestamp=0)
    assert state.current_node_id == "draw"
    assert [widget["type"] for widget in state.get_state_snapshot()["widgets"]] == ["drawing"]
    state.handle_gesture_events([event("two_fingers_swipe_left")], timestamp=1)
    assert state.current_node_id == "games"
