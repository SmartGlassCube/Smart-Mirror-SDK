"""The mirror app's settings: environment variables, plus a .env file when python-dotenv is installed
(./.env in the working directory, then backend/.env in a checkout of the repo).

See backend/.env.example for every variable.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from ..config.env import adopt_legacy_env
from ..config.paths import CHECKOUT_BACKEND_DIR

# A camera/microphone: None (the default device), a local device index, or an
# http:// URL served by scripts/lan_media_server.py on another machine.
Device = Union[int, str, None]


def device_from_env(name: str) -> Device:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value) if value.isdigit() else value


def flag_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value not in ("0", "false", "no", "off")


def load_dotenv_file() -> None:
    """Load ./.env, then backend/.env in a checkout, into os.environ.

    Variables already set win, and so does the first file. No-op without python-dotenv.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.cwd() / ".env")
    if CHECKOUT_BACKEND_DIR is not None:
        load_dotenv(CHECKOUT_BACKEND_DIR / ".env")
    adopt_legacy_env()  # a .env written before the rename still uses SMARTMIRROR_*


@dataclass(frozen=True)
class Settings:
    camera: Device = 0
    mic: Device = None

    # Any OpenAI-compatible endpoint; Ollama by default, so no paid API key is needed.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:0.5b"
    llm_api_key: str = "ollama"

    # MONGO_URI: the IEEE INSAT club content (events, news, ...) from the Dashboard repo's Mongo.
    content_mongo_uri: Optional[str] = None
    # GLASSCUBE_MONGO_READ_URI: a generic calendar collection, used when there's no club content.
    calendar_mongo_uri: Optional[str] = None
    calendar_mongo_db: str = "smartmirror"  # existing deployments keep their database
    calendar_mongo_collection: str = "events"

    # The voice assistant; it also needs the `assistant` extra (skipped with a warning without it).
    assistant: bool = True

    ws_port: int = 8080
    # In a checkout, start the frontend's Vite dev server along with the backend (dev convenience).
    # Otherwise the bundled, prebuilt UI is served on ws_port: http://localhost:8080.
    frontend: bool = True
    frontend_port: int = 5173

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv_file()
        defaults = cls()
        return cls(
            camera=device_from_env("GLASSCUBE_CAMERA") or defaults.camera,
            mic=device_from_env("GLASSCUBE_MIC"),
            llm_base_url=os.getenv("GLASSCUBE_LLM_BASE_URL", defaults.llm_base_url),
            llm_model=os.getenv("GLASSCUBE_LLM_MODEL", defaults.llm_model),
            llm_api_key=os.getenv("GLASSCUBE_LLM_API_KEY", defaults.llm_api_key),
            content_mongo_uri=os.getenv("MONGO_URI") or None,
            calendar_mongo_uri=os.getenv("GLASSCUBE_MONGO_READ_URI") or None,
            calendar_mongo_db=os.getenv("GLASSCUBE_MONGO_DB", defaults.calendar_mongo_db),
            calendar_mongo_collection=os.getenv("GLASSCUBE_MONGO_COLLECTION", defaults.calendar_mongo_collection),
            assistant=flag_from_env("GLASSCUBE_ASSISTANT", defaults.assistant),
            ws_port=int(os.getenv("GLASSCUBE_WS_PORT", defaults.ws_port)),
            frontend=flag_from_env("GLASSCUBE_FRONTEND", defaults.frontend),
            frontend_port=int(os.getenv("GLASSCUBE_FRONTEND_PORT", defaults.frontend_port)),
        )
