from smartmirror.smartmirror import SmartMirrorServer
from smartmirror.ui import WeatherWidget, CalendarWidget, NewsWidget, TextWidget
from smartmirror.cv.gestures import RaiseHandsGesture, FourFingersGesture, RaiseOneHandGesture
from smartmirror.assistant import Assistant

import asyncio

if __name__ == "__main__":
    weather = WeatherWidget.WeatherWidget(position={"x": 0.1, "y": 0.1})
    calendar = CalendarWidget.CalendarWidget(position={"x": 0.5, "y": 0.1})
    news = NewsWidget.NewsWidget(position={"x": 0.1, "y": 0.5})
    text = TextWidget.TextWidget(
        position={"x": 0.5, "y": 0.5},
        content="Welcome to Smart Mirror!",
        gestures=[RaiseHandsGesture.RaiseHandsGesture()]
    )

    graph = {
        "nodes": [
            {"id": "root", "widgets": [weather, calendar, news, text]},
            {"id": "achievements", "widgets": [TextWidget.TextWidget(content="Achievements!")]}
        ],
        "edges": [
            {"from": "root", "to": "achievements", "gesture": FourFingersGesture.FourFingersGesture()},
            {"from": "achievements", "to": "root", "gesture": RaiseHandsGesture.RaiseHandsGesture()}
        ]
    }

    assistant = Assistant.Assistant()

    server = SmartMirrorServer(graph=graph, assistant=assistant, edit_gesture=RaiseOneHandGesture.RaiseOneHandGesture())
    asyncio.run(server.run())