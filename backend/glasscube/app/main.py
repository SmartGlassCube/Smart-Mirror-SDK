"""Entry point: the `glasscube` command, or `python -m glasscube`.

    glasscube                       the demo mirror (Smart Mirror Studio's demo project)
    glasscube run my.glasscube.json a mirror designed in Smart Mirror Studio
    glasscube club                  the IEEE INSAT club's mirror (pages.py, content sync from MONGO_URI)
"""

import argparse
import asyncio
import dataclasses
import logging
import sys

from ..core import StateManager
from ..hal import HAL
from ..server import SmartMirrorServer
from ..server.static_ui import bundled_ui_dir
from .. import __version__
from ..project import ProjectError, load_project
from .demo import demo_project
from .frontend_dev import FrontendLauncher
from .pages import GESTURE_CONFIG, HOME, build_graph
from .settings import Settings

logger = logging.getLogger(__name__)


def build_assistant(settings, content_sync=None):
    """The voice chatbot. Ollama-backed by default, so it runs without a paid API key --
    pull a model first (e.g. `ollama pull qwen2.5:0.5b`) and start `ollama serve`.

    With `content_sync`, it retrieves from the Mongo-derived Qdrant collection and
    gets the live events/announcements prompt block instead of the seed corpus.

    None when disabled (GLASSCUBE_ASSISTANT=0) or when the `assistant` extra isn't installed.
    """
    if not settings.assistant:
        return None
    try:
        return _assistant(settings, content_sync)
    except ImportError as error:  # the `assistant` extra isn't installed
        logger.warning(
            "Voice assistant off: %s. Install it with `pip install \"glasscube[assistant]\"`, "
            "or set GLASSCUBE_ASSISTANT=0 to hide this.", error,
        )
        return None


def _assistant(settings, content_sync):
    from ..assistant import Assistant
    from ..assistant.llm import OpenAICompatBackend
    from ..assistant.rag import SEED_CORPUS_DIR

    hal = HAL(input_device=settings.mic)
    backend = OpenAICompatBackend(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
    if content_sync is not None:
        return Assistant(
            llm=backend, stt=True, tts=True, hal=hal,
            store=content_sync.indexer.store,
            extra_context=content_sync.prompt_block,
        )
    return Assistant(llm=backend, documents=str(SEED_CORPUS_DIR), stt=True, tts=True, hal=hal)


def build_content_sync(settings):
    """Club content from the Dashboard repo's Mongo (glasscube.content); None without MONGO_URI."""
    if not settings.content_mongo_uri:
        return None
    from ..content import build_content_sync as build  # needs the `data` extra

    return build()


def build_project_server(settings, project):
    """A mirror from a Smart Mirror Studio project: its pages, links, widgets and custom widgets."""
    return SmartMirrorServer(
        state_manager=project.state_manager(),
        widget_types=project.widget_types,
        camera_id=settings.camera,
        ws_port=settings.ws_port,
        assistant=build_assistant(settings),
    )


def build_server(settings):
    """The IEEE INSAT club's mirror (`glasscube club`): pages.py, plus club content when MONGO_URI is set."""
    content_sync = build_content_sync(settings)
    state_manager = StateManager(
        graph=build_graph(settings, content_sync),
        initial_node_id=HOME,
        gesture_config=GESTURE_CONFIG,
    )
    return SmartMirrorServer(
        state_manager=state_manager,
        camera_id=settings.camera,
        ws_port=settings.ws_port,
        assistant=build_assistant(settings, content_sync),
        content_sync=content_sync,
    )


async def run(server, frontend=None):
    if frontend is not None:
        await frontend.start()
    try:
        await server.run()
    finally:
        if frontend is not None:
            await frontend.stop()


def build_frontend(settings):
    """The Vite dev server in a checkout with npm; None when the bundled UI is served instead (or turned off)."""
    if not settings.frontend:
        return None
    launcher = FrontendLauncher(port=settings.frontend_port, ws_port=settings.ws_port)
    if launcher.available():
        return launcher
    if bundled_ui_dir() is not None:
        logger.info("Mirror UI on http://localhost:%s", settings.ws_port)
    else:
        logger.warning("No mirror UI: this install has no bundled UI and there's no frontend/ checkout to run.")
    return None


def parse_args(argv=None):
    # Options go before or after the command; SUPPRESS keeps a subcommand from resetting them.
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument("--port", type=int, default=argparse.SUPPRESS, help="WebSocket + UI port (GLASSCUBE_WS_PORT, default 8080)")
    options.add_argument("--camera", default=argparse.SUPPRESS, help="camera index or lan_media_server URL (GLASSCUBE_CAMERA)")
    options.add_argument("--no-assistant", action="store_true", default=argparse.SUPPRESS, help="don't start the voice assistant")

    parser = argparse.ArgumentParser(
        prog="glasscube",
        parents=[options],
        description="Run a gesture-controlled smart mirror. With no command, runs the demo mirror.",
    )
    parser.add_argument("--version", action="version", version=f"glasscube {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")
    run_command = commands.add_parser("run", parents=[options], help="run a mirror designed in Smart Mirror Studio")
    run_command.add_argument("project", help="a .glasscube.json or .glasscube.yaml file exported from the studio")
    commands.add_parser("demo", parents=[options], help="run the demo mirror (the default)")
    commands.add_parser("club", parents=[options], help="run the IEEE INSAT club's mirror (content from MONGO_URI)")
    return parser.parse_args(argv)


def apply_options(settings, args):
    changes = {}
    if hasattr(args, "port"):
        changes["ws_port"] = args.port
    if hasattr(args, "camera"):
        changes["camera"] = int(args.camera) if args.camera.isdigit() else args.camera
    if getattr(args, "no_assistant", False):
        changes["assistant"] = False
    return dataclasses.replace(settings, **changes)


def main(argv=None):
    args = parse_args(argv)
    # INFO on the glasscube.* loggers surfaces the voice pipeline's play-by-play
    # (VAD, raw Whisper transcripts, wake-word matches; see docs/voice-pipeline-testing.md).
    # Root stays at WARNING so third-party libraries don't drown it out.
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("glasscube").setLevel(logging.INFO)

    settings = apply_options(Settings.from_env(), args)
    try:
        if args.command == "club":
            server = build_server(settings)
        else:
            project = load_project(args.project) if args.command == "run" else demo_project()
            logger.info("Running %r (%d pages)", project.name, len(project.pages))
            server = build_project_server(settings, project)
    except ProjectError as error:
        sys.exit(f"glasscube: {error}")
    frontend = build_frontend(settings)
    try:
        asyncio.run(run(server, frontend))
    except KeyboardInterrupt:
        pass
