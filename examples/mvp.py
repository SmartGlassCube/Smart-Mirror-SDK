from smartmirror.smartmirror import SmartMirrorServer
from smartmirror.ui import WeatherWidget, CalendarWidget, NewsWidget, TextWidget, QRCodeGalleryWidget
from smartmirror.runtime.data_providers import QRCodeCatalogProvider, MongoCalendarProvider

import asyncio
import os


def fallback_calendar_provider(_widget=None):
    return {
        "events": [
            {"title": "Standup", "start": "2026-03-15T09:00:00"},
            {"title": "Build Review", "start": "2026-03-15T14:00:00"},
            {"title": "Daily Wrap", "start": "2026-03-15T18:00:00"},
        ]
    }

if __name__ == "__main__":
    mongo_uri = os.getenv("SMARTMIRROR_MONGO_READ_URI")

    if mongo_uri:
        calendar_provider = MongoCalendarProvider(
            uri=mongo_uri,
            database=os.getenv("SMARTMIRROR_MONGO_DB", "smartmirror"),
            collection=os.getenv("SMARTMIRROR_MONGO_COLLECTION", "events"),
            query={},
        )
        calendar_content = "Cloud calendar events"
    else:
        calendar_provider = fallback_calendar_provider
        calendar_content = "Fallback local events (set SMARTMIRROR_MONGO_READ_URI for cloud)"

    qr_provider = QRCodeCatalogProvider(
        {
            "tutorial": [
                {
                    "title": "Setup Guide",
                    "imageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/tutorial/setup",
                    "url": "https://example.com/tutorial/setup",
                },
                {
                    "title": "Gesture Basics",
                    "imageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/tutorial/gestures",
                    "url": "https://example.com/tutorial/gestures",
                },
            ],
            "project": [
                {
                    "title": "Main Repo",
                    "imageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/project/repo",
                    "url": "https://example.com/project/repo",
                }
            ],
        }
    )

    weather = WeatherWidget.WeatherWidget(position={"x": 0.1, "y": 0.2}, content="Static weather placeholder")
    calendar = CalendarWidget.CalendarWidget(
        position={"x": 0.5, "y": 0.2},
        content=calendar_content,
        data_provider=calendar_provider,
        refresh_interval=60,
    )
    news = NewsWidget.NewsWidget(position={"x": 0.1, "y": 0.5}, content="Static news placeholder")
    text = TextWidget.TextWidget(
        position={"x": 0.5, "y": 0.5},
        content="Welcome to Smart Mirror!"
    )
    qr_gallery = QRCodeGalleryWidget.QRCodeGalleryWidget(
        position={"x": 0.8, "y": 0.5},
        content="QR links by category",
        data_provider=qr_provider,
        refresh_interval=120,
    )

    graph = {
        "nodes": [
            {"id": "root", "widgets": [weather, calendar, news, text, qr_gallery]}
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