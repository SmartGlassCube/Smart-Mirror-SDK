# glasscube

Build gesture-controlled smart mirrors in Python. A webcam watches your hands,
[MediaPipe](https://developers.google.com/mediapipe) hand tracking turns their movement
into gestures (pinch, click, scroll, zoom, swipes), and those gestures move between
pages and drive widgets in a React UI that the package serves itself. An optional voice
assistant (wake word, Whisper, any OpenAI-compatible LLM, Piper TTS) answers out loud.

Everything runs locally: no account, no cloud service required.

## Install

```bash
pip install glasscube                 # gestures, pages, widgets, the server and its UI
pip install "glasscube[assistant]"    # + the voice assistant
pip install "glasscube[data]"         # + MongoDB providers and .env support
```

Python 3.9 or newer (3.10 to 3.12 for the `assistant` extra, whose speech models lag behind), and a webcam.

## Run the demo mirror

```bash
glasscube
```

Then open <http://localhost:8080> (full screen it on the mirror's display). Raise a hand
in front of the camera: the cursor follows your index finger, a two-finger swipe changes
page, a pinch grabs and moves a widget. Without a camera it still starts, with no gestures.

## Run a mirror designed without code

Design the pages, widgets and gestures in
[Smart Mirror Studio](https://github.com/SmartGlassCube/mirror-studio) (in the browser, with
webcam testing), export the project, then:

```bash
glasscube run my-mirror.glasscube.json      # or .yaml
```

Custom widgets written in the studio (by hand, from a template, or by its AI assistant) run
on the mirror as they did in the studio. Options for every command: `--port 8080`,
`--camera 1` (or a `scripts/lan_media_server.py` URL), `--no-assistant`. From Python:

```python
from glasscube.project import load_project
from glasscube.server import SmartMirrorServer

project = load_project("my-mirror.glasscube.json")
server = SmartMirrorServer(state_manager=project.state_manager(), widget_types=project.widget_types)
```

The voice assistant runs when the `assistant` extra is installed. It uses
[Ollama](https://ollama.com) by default (`ollama pull qwen2.5:0.5b`, then `ollama serve`);
point it at any OpenAI-compatible endpoint with `GLASSCUBE_LLM_BASE_URL`,
`GLASSCUBE_LLM_MODEL` and `GLASSCUBE_LLM_API_KEY`, or turn it off with
`GLASSCUBE_ASSISTANT=0`.

Settings are environment variables, also read from a `.env` file in the working directory
(with the `data` extra). The full list is in
[.env.example](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/backend/.env.example).
Runtime files (the downloaded hand model, the assistant's vector store) go in your user
data folder (`~/.local/share/glasscube`, `%LOCALAPPDATA%\glasscube` or
`~/Library/Application Support/glasscube`); move them with `GLASSCUBE_DATA_DIR`.

## Build your own mirror

A mirror is a graph: pages (nodes) hold widgets, and gestures (edges) move between them.

```python
import asyncio

from glasscube.server import SmartMirrorServer
from glasscube.widgets import CalendarWidget, TextWidget, WeatherWidget
from glasscube.widgets.providers import OpenMeteoWeatherProvider

weather = WeatherWidget(
    position={"x": 0.1, "y": 0.1},           # fractions of the screen
    data_provider=OpenMeteoWeatherProvider(city="Paris", latitude=48.86, longitude=2.35),
    refresh_interval=600,                    # seconds
)
agenda = CalendarWidget(
    position={"x": 0.6, "y": 0.1},
    # Any callable, sync or async: its result becomes the widget's data.
    data_provider=lambda: {"events": [{"title": "Standup", "start": "2026-11-18T09:00:00"}]},
    refresh_interval=60,
)
tips = TextWidget(
    position={"x": 0.5, "y": 0.5},
    content={"tips": ["Swipe to cycle", "Scroll for sections"], "about": ["Made with glasscube"]},
)

graph = {
    "nodes": [
        {"id": "home", "widgets": [weather, agenda]},
        {"id": "tips", "widgets": [tips]},
    ],
    "edges": [
        {"from": "home", "to": "tips", "gesture": "two_fingers_swipe_left"},
        {"from": "tips", "to": "home", "gesture": "two_fingers_swipe_right"},
    ],
}

asyncio.run(SmartMirrorServer(graph=graph).run())   # UI on http://localhost:8080
```

Built-in widgets: `TextWidget`, `WeatherWidget`, `CalendarWidget`, `NewsWidget`,
`EventsWidget`, `QRGalleryWidget`, `GamesWidget`, `DrawingWidget`. Built-in gestures:
`pinch_start/move/end`, `left_click`, `right_click`, `scroll_*`, `zoom_*`,
`swipe_left/right/up/down` and `two_fingers_swipe_left/right/up/down`.

### Your own gestures, widgets and reactions

```python
from glasscube.core import StateManager
from glasscube.vision import Gesture, GestureDetector, GestureEvent, SIDES, default_gesture_set

class FistGesture(Gesture):
    name = "fist"

    def __init__(self):
        self._was_fist = {side: False for side in SIDES}

    def detect(self, context):
        events = []
        for side in SIDES:
            hand = context.hands[side]
            fingers = ("index_up", "middle_up", "ring_up", "pinky_up")
            is_fist = hand.detected and not any(context.signals[f][side] for f in fingers)
            if is_fist and not self._was_fist[side]:
                events.append(GestureEvent(type="fist", hand=side, location=hand.palm_center))
            self._was_fist[side] = is_fist
        return events

state = StateManager(graph=graph, event_bindings={
    "fist": {"method": "set_current_node", "kwargs": {"node_id": "home"}},   # a fist goes home
})
detector = GestureDetector(gestures=default_gesture_set() + [FistGesture()])
server = SmartMirrorServer(state_manager=state, gesture_detector=detector)
```

A new widget type needs a React component on the UI side as well: see
[extending.md](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/docs/extending.md).

## Documentation

- [Architecture](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/docs/architecture.md): the camera → gestures → state → UI loop, module by module
- [Extending](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/docs/extending.md): gestures, widgets, pages, bindings
- [Vision](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/docs/vision.md): the hand signals and gesture tuning
- [Protocol](https://github.com/SmartGlassCube/Smart-Mirror-SDK/blob/main/docs/protocol.md): the WebSocket messages between backend and UI

## Developing the SDK

From a checkout of [the repository](https://github.com/SmartGlassCube/Smart-Mirror-SDK),
in `backend/`, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra data --extra assistant   # backend/.venv; plain `uv sync` = gestures + server only
uv run glasscube                       # also starts ../frontend's Vite dev server (needs npm)
uv run pytest                            # no camera needed
uv run python scripts/build_frontend.py  # bundle the UI into glasscube/ui/ before `uv build`
```

| Path | |
|---|---|
| `glasscube/app/` | The `glasscube` command (`main.py`): the demo (`demo.glasscube.json`), `run`, and the club's mirror (`pages.py`); `settings.py` (env vars) |
| `glasscube/project.py` | Loads Smart Mirror Studio projects into a `StateManager` |
| `glasscube/server/` | `SmartMirrorServer`: WebSocket, camera loop, widget refresh, assistant hooks, the bundled UI |
| `glasscube/{vision,core,widgets,assistant,content,hal,config}/` | The SDK pieces, usable on their own |
| `tests/` | One folder per package |
| `scripts/` | `lan_media_server.py` (share a camera/mic over the LAN), `content_sync_daemon.py`, `build_frontend.py`, checks |
| `examples/` | `gesture_detector_debug.py`: annotated camera window + gesture feed |

## License

MIT
