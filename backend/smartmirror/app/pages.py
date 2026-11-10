"""The mirror's pages and their widgets: draw <-> games <-> home <-> events."""

from ..widgets import (
    CalendarWidget,
    DrawingWidget,
    EventsWidget,
    GamesWidget,
    NewsWidget,
    QRGalleryWidget,
    TextWidget,
    WeatherWidget,
)
from ..widgets.providers import (
    MongoCalendarProvider,
    OpenMeteoWeatherProvider,
    QRCodeCatalogProvider,
)

HOME = "home"

GESTURE_CONFIG = {
    "target_radius": 0.40,
    "swipe_cooldown": 0.25,
    "scroll_cooldown": 0.20,
    "node_navigation_cooldown": 0.80,
}

QR_CATALOG = {
    "tutorial": [
        {
            "title": "IEEE INSAT CS Social Media",
            "imageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/tutorial/setup",
            "url": "https://example.com/tutorial/setup",
        },
    ],
    "project": [
        {
            "title": "Smart Mirror SDK",
            "imageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/project/repo",
            "url": "https://github.com/SmartGlassCube",
        }
    ],
}


def build_graph(settings, content_sync=None):
    """The page graph for StateManager. `content_sync` (club content from Mongo) feeds
    the calendar, news and events widgets; without it they show placeholders."""
    return {
        "nodes": [
            {"id": HOME, "widgets": home_widgets(settings, content_sync)},
            {"id": "games", "widgets": games_widgets()},
            {"id": "events", "widgets": events_widgets(content_sync)},
            {"id": "draw", "widgets": draw_widgets()},
        ],
        "edges": [
            *link(HOME, "games", gesture="two_fingers_swipe_right", back="two_fingers_swipe_left"),
            *link(HOME, "events", gesture="two_fingers_swipe_left", back="two_fingers_swipe_right"),
            *link("games", "draw", gesture="two_fingers_swipe_right", back="two_fingers_swipe_left"),
        ],
    }


def link(page, other, gesture, back):
    """Edges both ways between two pages: `gesture` goes page -> other, `back` returns."""
    return [
        {"from": page, "to": other, "gesture": gesture},
        {"from": other, "to": page, "gesture": back},
    ]


def home_widgets(settings, content_sync):
    # Live weather for Tunis from Open-Meteo (free, no API key), refreshed every 10 minutes.
    weather = WeatherWidget(
        position={"x": 0.1, "y": 0.2},
        data_provider=OpenMeteoWeatherProvider(city="Tunis", latitude=36.8065, longitude=10.1815),
        refresh_interval=600,
    )
    calendar = CalendarWidget(position={"x": 0.5, "y": 0.2}, refresh_interval=60, **calendar_source(settings, content_sync))
    if content_sync is not None:
        # Active announcements, then achievements, of the SB and its chapters.
        news = NewsWidget(
            position={"x": 0.1, "y": 0.5},
            data_provider=lambda _widget=None: {"items": content_sync.news()},
            refresh_interval=30,
        )
    else:
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
        data_provider=QRCodeCatalogProvider(QR_CATALOG),
        refresh_interval=120,
    )
    return [weather, calendar, news, text, qr_gallery]


def calendar_source(settings, content_sync):
    """The calendar widget's `content` + `data_provider`: club events, a Mongo calendar, or placeholders."""
    if content_sync is not None:
        # The club's events from the dashboard, keyed by day: {"2026-10-28": [event, ...]}.
        return {
            "content": "IEEE INSAT events",
            "data_provider": lambda _widget=None: {"days": content_sync.calendar_days()},
        }
    if settings.calendar_mongo_uri:
        return {
            "content": "Cloud calendar events",
            "data_provider": MongoCalendarProvider(
                uri=settings.calendar_mongo_uri,
                database=settings.calendar_mongo_db,
                collection=settings.calendar_mongo_collection,
                query={},
            ),
        }
    return {
        "content": "Fallback local events (set SMARTMIRROR_MONGO_READ_URI for cloud)",
        "data_provider": placeholder_calendar,
    }


def placeholder_calendar():
    return {
        "events": [
            {"title": "Standup", "start": "2026-03-15T09:00:00"},
            {"title": "Build Review", "start": "2026-03-15T14:00:00"},
            {"title": "Daily Wrap", "start": "2026-03-15T18:00:00"},
        ]
    }


def games_widgets():
    # Placeholder slots until the computer-vision games exist; give each one an "icon" image URL.
    return [
        GamesWidget(
            position={"x": 0.5, "y": 0.4},
            games=[{"id": f"game-{n}", "title": "Coming soon"} for n in range(1, 7)],
            draggable=False,
        )
    ]


def draw_widgets():
    # The only widget on its page: a pinch anywhere draws instead of grabbing another widget.
    return [DrawingWidget(position={"x": 0.5, "y": 0.44})]


def events_widgets(content_sync):
    if content_sync is not None:
        # Every event, upcoming then past, with its image (a "?" placeholder without one).
        return [
            EventsWidget(
                position={"x": 0.5, "y": 0.4},
                data_provider=lambda _widget=None: {"items": content_sync.event_cards()},
                refresh_interval=30,
                draggable=False,
            )
        ]
    # Placeholder cards until MONGO_URI is set.
    return [
        EventsWidget(
            position={"x": 0.5, "y": 0.4},
            items=[
                {"id": f"event-{n}", "name": "Event name", "description": "Description from the club database."}
                for n in range(1, 4)
            ],
            draggable=False,
        )
    ]
