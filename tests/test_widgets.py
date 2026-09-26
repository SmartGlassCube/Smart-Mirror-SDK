import asyncio

from smartmirror.server.widget_data import refresh_widget_data
from smartmirror.widgets import BaseWidget, CalendarWidget, GamesWidget, TextWidget


def test_games_widget_serializes_games():
    games = [{"id": "pong", "title": "Pong", "icon": "/pong.png"}]
    serialized = GamesWidget(games=games).serialize()
    assert serialized["type"] == "games"
    assert serialized["data"] == {"games": games}
    assert GamesWidget().serialize()["data"] == {"games": []}


def test_text_widget_modes():
    assert TextWidget(content="static").serialize()["content"] == "static"
    assert not TextWidget(content="static").apply_navigation(horizontal_steps=1)

    items = TextWidget(content=["a", "", "b"])
    assert items.apply_navigation(horizontal_steps=1) and items.content == "b"
    assert items.apply_navigation(horizontal_steps=1) and items.content == "a"  # wraps

    sections = TextWidget(content={"x": ["x1", "x2"], "y": ["y1"]}, metadata={"theme": "dark"})
    sections.apply_navigation(horizontal_steps=1)
    sections.apply_navigation(vertical_steps=1)
    metadata = sections.serialize()["metadata"]
    assert sections.content == "y1"
    assert metadata["key"] == "y" and metadata["itemIndex"] == 0 and metadata["theme"] == "dark"


def test_minimal_custom_widget():
    class ClockWidget(BaseWidget):
        type = "clock"
        refresh_interval = 1

    clock = ClockWidget(position={"x": 0.9, "y": 0.1}, content="12:00")
    serialized = clock.serialize()

    assert serialized["type"] == "clock" and serialized["id"].startswith("clock-")
    assert clock.refresh_interval == 1 and CalendarWidget().refresh_interval == 60
    assert BaseWidget(widget_type="banner").type == "banner"


def test_data_providers_sync_async_and_argless():
    async def async_provider(widget):
        return {"from": widget.type}

    widgets = [
        CalendarWidget(data_provider=lambda widget: {"events": []}),
        TextWidget(data_provider=async_provider),
        BaseWidget(widget_type="plain", data_provider=lambda: 42),
    ]

    assert asyncio.run(refresh_widget_data(widgets))
    assert [w.data for w in widgets] == [{"events": []}, {"from": "text"}, 42]
    assert not asyncio.run(refresh_widget_data(widgets))  # not due yet


def test_failing_provider_does_not_break_refresh():
    def broken(widget):
        raise TypeError("bug inside the provider")

    widget = CalendarWidget(data_provider=broken, data={"events": ["kept"]})

    assert not asyncio.run(refresh_widget_data([widget]))
    assert widget.data == {"events": ["kept"]}
