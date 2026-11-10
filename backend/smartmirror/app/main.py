"""Entry point: `python -m smartmirror` (from backend/)."""

import asyncio
import logging

from ..assistant import Assistant
from ..assistant.llm import OpenAICompatBackend
from ..assistant.rag import SEED_CORPUS_DIR
from ..core import StateManager
from ..hal import HAL
from ..server import SmartMirrorServer
from .frontend_dev import FrontendLauncher
from .pages import GESTURE_CONFIG, HOME, build_graph
from .settings import Settings


def build_assistant(settings, content_sync=None):
    """The voice chatbot. Ollama-backed by default, so it runs without a paid API key --
    pull a model first (e.g. `ollama pull qwen2.5:0.5b`) and start `ollama serve`.

    With `content_sync`, it retrieves from the Mongo-derived Qdrant collection and
    gets the live events/announcements prompt block instead of the seed corpus.
    """
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
    """Club content from the Dashboard repo's Mongo (smartmirror.content); None without MONGO_URI."""
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


def main():
    # INFO on the smartmirror.* loggers surfaces the voice pipeline's play-by-play
    # (VAD, raw Whisper transcripts, wake-word matches; see docs/voice-pipeline-testing.md).
    # Root stays at WARNING so third-party libraries don't drown it out.
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("smartmirror").setLevel(logging.INFO)

    settings = Settings.from_env()
    server = build_server(settings)
    frontend = (
        FrontendLauncher(port=settings.frontend_port, ws_port=settings.ws_port) if settings.frontend else None
    )
    asyncio.run(run(server, frontend))
