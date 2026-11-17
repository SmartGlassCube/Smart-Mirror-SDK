import asyncio
import json
from datetime import date, datetime

import pytest
import websockets

from glasscube.app.demo import demo_project
from glasscube.app.main import apply_options, parse_args
from glasscube.app.settings import Settings
from glasscube.project import ProjectError, build_widget, load_project, parse_project
from glasscube.server import SmartMirrorServer
from glasscube.vision import GestureEvent
from glasscube.widgets import DrawingWidget, TextWidget, WeatherWidget
from glasscube.widgets.providers import ClockProvider, HttpJsonProvider, OpenMeteoWeatherProvider
from glasscube.widgets.providers.http_json import pick


def project_dict(**overrides):
    project = {
        "format": "glasscube-project",
        "version": 1,
        "name": "Test mirror",
        "settings": {"initialPage": "b", "gestureConfig": {"node_navigation_cooldown": 0, "unknown": 1}},
        "pages": [
            {"id": "a", "widgets": [{"id": "t", "type": "text", "position": {"x": 0.2, "y": 0.3}, "content": ["one", "two"]}]},
            {"id": "b", "widgets": [{"id": "g", "type": "greeting", "props": {"name": "Ada"}, "data": {"kind": "static", "value": 7}}]},
        ],
        "edges": [
            {"id": "e1", "from": "b", "to": "a", "gesture": "two_fingers_swipe_left"},
            {"id": "e2", "from": "a", "to": "ghost", "gesture": "two_fingers_swipe_right"},
        ],
        "bindings": [{"id": "b1", "gesture": "right_click", "action": {"kind": "goto", "page": "b"}}],
        "widgetTypes": [
            {"type": "greeting", "name": "Greeting", "source": "...", "compiled": "exports.default = () => null"},
            {"type": "broken", "name": "Broken", "source": "...", "compiled": None},
        ],
    }
    project.update(overrides)
    return project


def gesture(name):
    return GestureEvent(type=name, hand="right", location=(0.5, 0.5))


def test_a_project_becomes_pages_links_and_any_page_gestures():
    project = parse_project(project_dict())
    state = project.state_manager()

    assert state.current_node_id == "b"  # settings.initialPage
    assert project.gesture_config == {"node_navigation_cooldown": 0}
    assert [edge["id"] for edge in project.edges] == ["e1"]  # the link to a missing page is dropped
    assert project.widget_types == [{"type": "greeting", "name": "Greeting", "code": "exports.default = () => null"}]

    state.handle_gesture_events([gesture("two_fingers_swipe_left")], timestamp=0)
    assert state.current_node_id == "a"
    state.handle_gesture_events([gesture("right_click")], timestamp=1)  # "any page" gesture
    assert state.current_node_id == "b"

    widget = state.get_state_snapshot()["widgets"][0]
    assert widget == {**widget, "id": "g", "type": "greeting", "data": 7, "metadata": {"name": "Ada"}}


def test_widgets_get_their_sdk_class_and_data_provider():
    text = build_widget({"type": "text", "content": {"tips": ["a", "b"]}})
    assert isinstance(text, TextWidget) and text.content == "a"

    weather = build_widget({"type": "weather", "data": {"kind": "weather", "city": "Oslo", "latitude": 59.9, "longitude": 10.7}})
    assert isinstance(weather, WeatherWidget) and isinstance(weather.data_provider, OpenMeteoWeatherProvider)
    assert weather.data_provider.city == "Oslo"

    clock = build_widget({"type": "clock", "data": {"kind": "clock", "hour12": True}, "refreshInterval": 60})
    assert isinstance(clock.data_provider, ClockProvider) and clock.refresh_interval == 1 and "time" in clock.data

    api = build_widget({"type": "quote", "data": {"kind": "http", "url": "https://example.com/q", "path": "quotes.0"}})
    assert isinstance(api.data_provider, HttpJsonProvider) and api.data_provider.path == "quotes.0"

    games = build_widget({"type": "games", "data": {"kind": "static", "value": {"games": [{"id": "x"}]}}, "draggable": False})
    assert games.data == {"games": [{"id": "x"}]} and games.draggable is False

    drawing = build_widget({"type": "drawing", "position": {"x": 0, "y": 0}, "draggable": True})
    assert isinstance(drawing, DrawingWidget) and drawing.draggable is False and drawing.data["clears"] == 0

    assert build_widget({"type": "news", "position": {"x": 7, "y": "?"}}).position == {"x": 1.0, "y": 0.5}


def test_clock_and_json_path_match_the_studio():
    now = datetime(2026, 11, 17, 14, 5, 7)
    assert ClockProvider()(now=now) == {**ClockProvider()(now=now), "time": "14:05", "seconds": "07", "date": "Tuesday 17 November"}
    assert ClockProvider(hour12=True)(now=now)["time"] == "2:05 PM"
    assert ClockProvider(hour12=True)(now=datetime(2026, 1, 1, 0, 30))["time"] == "12:30 AM"

    body = {"quotes": [{"text": "hi"}], "n": 1}
    assert pick(body, "quotes.0.text") == "hi"
    assert pick(body, "") == body
    assert pick(body, "quotes.4") is None and pick(body, "n.x") is None


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"hello": 1}, "Not a Smart Mirror Studio project"),
        (project_dict(version=99), "newer glasscube"),
        (project_dict(pages=[]), "no pages"),
    ],
)
def test_bad_files_are_explained(raw, message):
    with pytest.raises(ProjectError, match=message):
        parse_project(raw)


def test_json_yaml_and_pre_rename_files_load(tmp_path):
    import yaml

    (tmp_path / "m.glasscube.json").write_text(json.dumps(project_dict()))
    (tmp_path / "m.glasscube.yaml").write_text(yaml.safe_dump(project_dict(format="smartmirror-project")))
    (tmp_path / "bad.json").write_text("{not json")

    assert load_project(tmp_path / "m.glasscube.json").initial_page == "b"
    assert load_project(tmp_path / "m.glasscube.yaml").name == "Test mirror"
    with pytest.raises(ProjectError, match="not valid JSON"):
        load_project(tmp_path / "bad.json")
    with pytest.raises(ProjectError, match="Can't read"):
        load_project(tmp_path / "missing.json")


def test_the_demo_is_the_studio_demo_with_todays_agenda():
    project = demo_project(today=date(2030, 5, 1))
    assert [page["id"] for page in project.pages] == ["home", "agenda", "draw"]
    assert {t["type"] for t in project.widget_types} == {"clock", "greeting"}

    calendar = next(w for w in project.pages[1]["widgets"] if w["type"] == "calendar")
    starts = sorted(event["start"] for event in calendar["data"]["value"]["events"])
    assert starts[0].startswith("2030-05-01")

    state = project.state_manager()
    types = [w["type"] for w in state.get_state_snapshot()["widgets"]]
    assert types == ["clock", "weather", "greeting", "text"]


def test_command_line_options_and_commands():
    args = parse_args(["--port", "9000", "run", "x.glasscube.json", "--camera", "2", "--no-assistant"])
    assert (args.command, args.project) == ("run", "x.glasscube.json")
    settings = apply_options(Settings(), args)
    assert (settings.ws_port, settings.camera, settings.assistant) == (9000, 2, False)

    assert parse_args([]).command is None  # the demo
    assert apply_options(Settings(), parse_args(["club"])) == Settings()
    assert apply_options(Settings(), parse_args(["demo", "--camera", "http://pi:8000"])).camera == "http://pi:8000"


def test_server_sends_custom_widgets_before_the_first_state():
    project = parse_project(project_dict())
    server = SmartMirrorServer(with_camera=False, serve_ui=False, state_manager=project.state_manager(),
                               widget_types=project.widget_types)

    async def main():
        async with websockets.serve(server.hub.handle_client, "127.0.0.1", 0) as ws_server:
            port = ws_server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                return json.loads(await ws.recv()), json.loads(await ws.recv())

    types, init = asyncio.run(main())
    assert types == {"type": "WIDGET_TYPES", "widgetTypes": project.widget_types}
    assert init["type"] == "INIT" and init["state"]["nodeId"] == "b"
