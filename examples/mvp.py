import asyncio
import logging
import os
from pathlib import Path

from smartmirror.assistant import Assistant
from smartmirror.assistant.llm import OpenAICompatBackend
from smartmirror.core import StateManager
from smartmirror.server import SmartMirrorServer
from smartmirror.widgets import (
    CalendarWidget,
    EventsWidget,
    GamesWidget,
    NewsWidget,
    QRGalleryWidget,
    TextWidget,
    WeatherWidget,
)
from smartmirror.widgets.providers import MongoCalendarProvider, OpenMeteoWeatherProvider, QRCodeCatalogProvider

# INFO on the smartmirror.* loggers surfaces the voice pipeline's own
# play-by-play (VAD detections, raw Whisper transcripts, wake-word
# match/no-match) -- see scripts/voice_pipeline_manual_test.md for what to
# expect. Root stays at WARNING so third-party libraries (httpx,
# sentence_transformers, pywhispercpp, ...) don't drown it out.
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("smartmirror").setLevel(logging.INFO)

try:  # optional: `pip install -e ".[data]"` to read SMARTMIRROR_* settings from a .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def build_assistant(content_sync=None):
    """Ollama-backed by default so this runs without a paid API key -- pull a
    model first (e.g. `ollama pull qwen2.5:0.5b`) and start `ollama serve`.
    Override via env vars to point at OpenAI or any other OpenAI-compatible
    endpoint instead.

    When `content_sync` is set (MONGO_URI env var present, see __main__),
    the assistant retrieves from the Mongo-derived Qdrant collection and
    gets the live events/announcements/mission prompt block instead of the
    placeholder seed corpus.
    """
    backend = OpenAICompatBackend(
        api_key=os.getenv("SMARTMIRROR_LLM_API_KEY", "ollama"),
        base_url=os.getenv("SMARTMIRROR_LLM_BASE_URL", "http://localhost:11434/v1"),
        model=os.getenv("SMARTMIRROR_LLM_MODEL", "qwen2.5:0.5b"),
    )
    if content_sync is not None:
        return Assistant(
            llm=backend, stt=True, tts=True,
            store=content_sync.indexer.store,
            extra_context=content_sync.prompt_block,
        )
    seed_corpus = Path(__file__).resolve().parent.parent / "smartmirror" / "assistant" / "rag" / "seed_corpus"
    return Assistant(llm=backend, documents=str(seed_corpus), stt=True, tts=True)


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

    # Separate from the generic personal-calendar Mongo above: this is the IEEE
    # INSAT club content sync (events/announcements/about/achievements/board),
    # opt-in via MONGO_URI. See smartmirror/content/ and infra/mongo/CONTRACT.md.
    content_sync = None
    if os.getenv("MONGO_URI"):
        from smartmirror.content import build_content_sync

        content_sync = build_content_sync()

    qr_provider = QRCodeCatalogProvider(
        {
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
    )

    # Live weather for Tunis from Open-Meteo (free, no API key), refreshed every 10 minutes.
    weather = WeatherWidget(
        position={"x": 0.1, "y": 0.2},
        data_provider=OpenMeteoWeatherProvider(city="Tunis", latitude=36.8065, longitude=10.1815),
        refresh_interval=600,
    )
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

    # Placeholder slots until the computer-vision games exist; give each one an "icon" image URL.
    games = GamesWidget(
        position={"x": 0.5, "y": 0.4},
        games=[{"id": f"game-{n}", "title": "Coming soon"} for n in range(1, 7)],
        draggable=False,
    )

    if content_sync is not None:
        events = EventsWidget(
            position={"x": 0.5, "y": 0.4},
            data_provider=lambda _widget=None: {
                "items": [
                    {"id": f"events:{doc['_id']}", "name": doc["title"], "description": doc["description"]}
                    for doc in content_sync.widget_data("events")
                ]
            },
            refresh_interval=30,
            draggable=False,
        )
    else:
        # Placeholder cards until MONGO_URI is set. Later, pass a `data_provider`
        # returning {"items": [{"id", "name", "description", "image"}]} instead of `items`.
        events = EventsWidget(
            position={"x": 0.5, "y": 0.4},
            items=[
                {"id": f"event-{n}", "name": "Event name", "description": "Description from the club database."}
                for n in range(1, 4)
            ],
            draggable=False,
        )

    # Focus mode is not in the graph anymore. To bring it back, add `focus_page` to
    # "nodes" and `focus_edges` to "edges" (and free up the swipe it uses from home).
    focus_page = {"id": "focus", "widgets": [focus_text]}
    focus_edges = [
        {"from": "home", "to": "focus", "gesture": "two_fingers_swipe_left"},
        {"from": "focus", "to": "home", "gesture": "two_fingers_swipe_right"},
    ]

    # games <-> home <-> events
    graph = {
        "nodes": [
            {"id": "home", "widgets": [weather, calendar, news, text, qr_gallery]},
            {"id": "games", "widgets": [games]},
            {"id": "events", "widgets": [events]},
        ],
        "edges": [
            {
                "from": "home",
                "to": "games",
                "gesture": "two_fingers_swipe_right",
            },
            {
                "from": "games",
                "to": "home",
                "gesture": "two_fingers_swipe_left",
            },
            {
                "from": "home",
                "to": "events",
                "gesture": "two_fingers_swipe_left",
            },
            {
                "from": "events",
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

    server = SmartMirrorServer(
        state_manager=state_manager,
        with_frontend=True,
        with_camera=True,
        assistant=build_assistant(content_sync),
        content_sync=content_sync,
    )
    asyncio.run(server.run())
