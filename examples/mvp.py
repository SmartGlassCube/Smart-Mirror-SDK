from smartmirror.smartmirror import SmartMirrorServer
from smartmirror.ui import WeatherWidget, CalendarWidget, NewsWidget, TextWidget

import asyncio

if __name__ == "__main__":
    weather = WeatherWidget.WeatherWidget(position={"x": 0.1, "y": 0.2})
    calendar = CalendarWidget.CalendarWidget(position={"x": 0.5, "y": 0.2})
    news = NewsWidget.NewsWidget(position={"x": 0.1, "y": 0.5})
    text = TextWidget.TextWidget(
        position={"x": 0.5, "y": 0.5},
        content="Welcome to Smart Mirror!"
    )

    graph = {
        "nodes": [
            {"id": "root", "widgets": [weather, calendar, news, text]}
        ],
        "edges": []
    }

    server = SmartMirrorServer(
        graph=graph,
        with_ui=True,
        with_camera=False,
        with_microphone=False,
        assistant=None,
        edit_gesture=None,
    )
    asyncio.run(server.run())