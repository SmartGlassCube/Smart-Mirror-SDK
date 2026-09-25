import asyncio
import os

from smartmirror.core import StateManager
from smartmirror.server import SmartMirrorServer
from smartmirror.widgets import CalendarWidget, NewsWidget, QRGalleryWidget, TextWidget, WeatherWidget
from smartmirror.widgets.providers import MongoCalendarProvider, QRCodeCatalogProvider

try:  # optional: `pip install -e ".[data]"` to read SMARTMIRROR_* settings from a .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def fallback_calendar_provider():
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

    weather = WeatherWidget(position={"x": 0.1, "y": 0.2}, content="Static weather placeholder")
    calendar = CalendarWidget(
        position={"x": 0.5, "y": 0.2},
        content=calendar_content,
        data_provider=calendar_provider,
        refresh_interval=60,
    )
    news = NewsWidget(position={"x": 0.1, "y": 0.5}, content="Static news placeholder")
    text = TextWidget(
        position={"x": 0.5, "y": 0.5},
        content={
            "home": [
                "Welcome to Smart Mirror!",
                "Swipe left/right for text items",
                "Scroll up/down for sections",
            ],
            "focus": [
                "Focus mode activated",
                "Use two fingers and swipe right to go back",
            ],
        },
    )
    qr_gallery = QRGalleryWidget(
        position={"x": 0.8, "y": 0.5},
        content="QR links by category",
        data_provider=qr_provider,
        refresh_interval=120,
    )

    focus_text = TextWidget(
        position={"x": 0.5, "y": 0.45},
        content=[
            "Focus board",
            "Main objective: ship gesture UX",
            "Keep hand posture steady for reliable input",
        ],
    )

    graph = {
        "nodes": [
            {"id": "home", "widgets": [weather, calendar, news, text, qr_gallery]},
            {"id": "focus", "widgets": [focus_text]},
        ],
        "edges": [
            {
                "from": "home",
                "to": "focus",
                "gesture": "two_fingers_swipe_left",
            },
            {
                "from": "focus",
                "to": "home",
                "gesture": "two_fingers_swipe_right",
            },
        ],
    }

    state_manager = StateManager(
        graph=graph,
        initial_node_id="home",
        gesture_config={
            "target_radius": 0.40,
            "swipe_cooldown": 0.25,
            "scroll_cooldown": 0.20,
            "node_navigation_cooldown": 0.80,
        },
    )

    server = SmartMirrorServer(state_manager=state_manager, with_frontend=True, with_camera=True)
    asyncio.run(server.run())