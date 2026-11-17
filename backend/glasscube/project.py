"""Mirror projects designed in Smart Mirror Studio: `*.glasscube.json` / `*.glasscube.yaml` files.

    from glasscube.project import load_project
    from glasscube.server import SmartMirrorServer

    project = load_project("my-mirror.glasscube.json")
    server = SmartMirrorServer(state_manager=project.state_manager(), widget_types=project.widget_types)

or, from a terminal, `glasscube run my-mirror.glasscube.json`.

A project maps one to one onto the SDK: pages are graph nodes, edges are graph edges,
"any page" gestures are `event_bindings`, each widget is a `BaseWidget` (or the matching
built-in class) with a data provider for its data source, and custom widget types are
React components the mirror UI loads at runtime (see `widget_types`).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .core import StateManager
from .widgets import (
    BaseWidget,
    CalendarWidget,
    DrawingWidget,
    EventsWidget,
    GamesWidget,
    NewsWidget,
    QRGalleryWidget,
    TextWidget,
    WeatherWidget,
)
from .widgets.providers import ClockProvider, HttpJsonProvider, OpenMeteoWeatherProvider

logger = logging.getLogger(__name__)

# "smartmirror-project": files exported before the SDK was renamed glasscube.
FORMATS = ("glasscube-project", "smartmirror-project")
VERSION = 1

BUILTIN_WIDGETS = {
    widget.type: widget
    for widget in (
        CalendarWidget,
        DrawingWidget,
        EventsWidget,
        GamesWidget,
        NewsWidget,
        QRGalleryWidget,
        TextWidget,
        WeatherWidget,
    )
}

GESTURE_CONFIG_KEYS = (
    "target_radius",
    "swipe_cooldown",
    "scroll_cooldown",
    "node_navigation_cooldown",
    "scroll_velocity_threshold",
    "allow_unmatched_single_edge_navigation",
)


class ProjectError(ValueError):
    """The file isn't a project this version of glasscube can run."""


@dataclass
class Project:
    name: str
    pages: List[Dict[str, Any]]  # as in the file
    edges: List[Dict[str, Any]]
    bindings: List[Dict[str, Any]]
    initial_page: str
    gesture_config: Dict[str, Any]
    # Custom widgets for the mirror UI: [{"type", "name", "code"}], `code` being the compiled
    # CommonJS module whose default export is the React component. SmartMirrorServer sends it.
    widget_types: List[Dict[str, str]] = field(default_factory=list)
    source: Optional[Path] = None

    def graph(self) -> Dict[str, Any]:
        """The page graph for `StateManager`, with fresh widget objects."""
        custom = {widget_type["type"] for widget_type in self.widget_types}
        return {
            "nodes": [
                {"id": page["id"], "widgets": [build_widget(widget, custom) for widget in page.get("widgets", [])]}
                for page in self.pages
            ],
            "edges": [{"from": edge["from"], "to": edge["to"], "gesture": edge["gesture"]} for edge in self.edges],
        }

    def event_bindings(self) -> Dict[str, List[Dict[str, Any]]]:
        """"Any page" gestures: each shows its page from wherever the mirror is."""
        bindings: Dict[str, List[Dict[str, Any]]] = {}
        for binding in self.bindings:
            action = {"method": "set_current_node", "kwargs": {"node_id": binding["action"]["page"]}}
            bindings.setdefault(binding["gesture"], []).append(action)
        return bindings

    def state_manager(self, **kwargs) -> StateManager:
        return StateManager(
            graph=self.graph(),
            initial_node_id=self.initial_page,
            gesture_config=self.gesture_config,
            event_bindings=self.event_bindings(),
            **kwargs,
        )


def load_project(path: Union[str, Path]) -> Project:
    """Read a project file exported by Smart Mirror Studio (JSON or YAML)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProjectError(f"Can't read {path}: {error.strerror or error}") from error
    project = parse_project(_decode(text, path), source=path)
    return project


def _decode(text: str, path: Path) -> Any:
    if text.lstrip().startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise ProjectError(f"{path.name} is not valid JSON: {error}") from error
    try:
        import yaml
    except ImportError as error:  # a dependency, so only in an unusual install
        raise ProjectError("Reading YAML projects needs PyYAML (pip install pyyaml), or export JSON") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ProjectError(f"{path.name} is not valid YAML: {error}") from error


def parse_project(raw: Any, source: Optional[Path] = None) -> Project:
    """Check a decoded project file and fill in the defaults the studio would."""
    if not isinstance(raw, dict) or raw.get("format") not in FORMATS:
        raise ProjectError("Not a Smart Mirror Studio project (export it from the studio's Export menu)")
    version = raw.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise ProjectError(f"This project needs a newer glasscube (project version {version}); try `pip install -U glasscube`")

    pages = [page for page in raw.get("pages") or [] if isinstance(page, dict) and isinstance(page.get("id"), str)]
    if not pages:
        raise ProjectError("The project has no pages")
    page_ids = {page["id"] for page in pages}

    edges = []
    for edge in _dicts(raw.get("edges")):
        if edge.get("from") in page_ids and edge.get("to") in page_ids and isinstance(edge.get("gesture"), str):
            edges.append(edge)
        else:
            logger.warning("Skipping a link that doesn't join two pages of the project: %s", edge)

    bindings = []
    for binding in _dicts(raw.get("bindings")):
        action = binding.get("action")
        if isinstance(binding.get("gesture"), str) and isinstance(action, dict) and action.get("page") in page_ids:
            bindings.append(binding)
        else:
            logger.warning("Skipping an \"any page\" gesture to a missing page: %s", binding)

    widget_types = []
    for widget_type in _dicts(raw.get("widgetTypes")):
        name = widget_type.get("type")
        if not isinstance(name, str):
            continue
        if not widget_type.get("compiled"):
            logger.warning(
                "Custom widget %r has no compiled code (fix its errors in the studio and export again); it won't show.",
                name,
            )
            continue
        widget_types.append({"type": name, "name": str(widget_type.get("name") or name), "code": widget_type["compiled"]})

    custom = {widget_type["type"] for widget_type in _dicts(raw.get("widgetTypes"))}
    for page in pages:
        for widget in _dicts(page.get("widgets")):
            kind = widget.get("type")
            if kind not in BUILTIN_WIDGETS and kind not in custom:
                logger.warning("Page %r: unknown widget type %r; it won't show.", page["id"], kind)

    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    initial = settings.get("initialPage")
    gesture_config = settings.get("gestureConfig") if isinstance(settings.get("gestureConfig"), dict) else {}

    return Project(
        name=str(raw.get("name") or "Mirror"),
        pages=pages,
        edges=edges,
        bindings=bindings,
        initial_page=initial if initial in page_ids else pages[0]["id"],
        gesture_config={key: gesture_config[key] for key in GESTURE_CONFIG_KEYS if key in gesture_config},
        widget_types=widget_types,
        source=source,
    )


def build_widget(widget: Dict[str, Any], custom_types=()) -> BaseWidget:
    """One widget of a project page, as the SDK object the StateManager drives."""
    kind = widget.get("type")
    position = widget.get("position") if isinstance(widget.get("position"), dict) else {}
    options = {
        "position": {"x": _fraction(position.get("x")), "y": _fraction(position.get("y"))},
        "metadata": widget.get("props") if isinstance(widget.get("props"), dict) else {},
        "draggable": widget.get("draggable") is not False,
        "widget_id": widget.get("id"),
    }
    try:
        options["refresh_interval"] = max(1.0, float(widget.get("refreshInterval") or 300))
    except (TypeError, ValueError):
        options["refresh_interval"] = 300.0

    if kind == "drawing":
        # Holds its own brush state as `data`; a pinch draws, so it never drags.
        options.pop("draggable")
        return DrawingWidget(**options)
    if kind == "text":
        return TextWidget(content=widget.get("content"), **options)

    cls = BUILTIN_WIDGETS.get(kind)
    built = cls(content=widget.get("content"), **options) if cls else BaseWidget(
        widget_type=kind, content=widget.get("content"), **options
    )
    apply_data_source(built, widget.get("data"))
    return built


def apply_data_source(widget: BaseWidget, source: Any) -> None:
    """Set a widget's `data` (fixed JSON) or `data_provider` (weather, clock, JSON API)."""
    if not isinstance(source, dict):
        return
    kind = source.get("kind")
    if kind == "static":
        widget.data = source.get("value")
    elif kind == "weather":
        widget.data_provider = OpenMeteoWeatherProvider(
            latitude=source.get("latitude"), longitude=source.get("longitude"), city=source.get("city") or ""
        )
    elif kind == "clock":
        widget.data_provider = ClockProvider(hour12=bool(source.get("hour12")))
        widget.data = widget.data_provider()
        widget.refresh_interval = 1
    elif kind == "http" and source.get("url"):
        widget.data_provider = HttpJsonProvider(source["url"], path=source.get("path") or "")
    elif kind not in (None, "none", "http"):
        logger.warning("Widget %s: unknown data source %r", widget.id, kind)


def _dicts(value) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _fraction(value, default=0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, number))
