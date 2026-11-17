"""Entry point: the `glasscube` command, or `python -m glasscube`."""

import asyncio
import logging

from ..core import StateManager
from ..hal import HAL
from ..server import SmartMirrorServer
from ..server.static_ui import bundled_ui_dir
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


def build_server(settings):
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


def main():
    # INFO on the glasscube.* loggers surfaces the voice pipeline's play-by-play
    # (VAD, raw Whisper transcripts, wake-word matches; see docs/voice-pipeline-testing.md).
    # Root stays at WARNING so third-party libraries don't drown it out.
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("glasscube").setLevel(logging.INFO)

    settings = Settings.from_env()
    server = build_server(settings)
    frontend = build_frontend(settings)
    try:
        asyncio.run(run(server, frontend))
    except KeyboardInterrupt:
        pass
