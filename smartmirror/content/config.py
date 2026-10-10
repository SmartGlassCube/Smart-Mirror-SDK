"""Configuration for the Mongo content sync, read from env vars with sane defaults.

The mirror runs exactly as today (seed corpus, no sync) unless MONGO_URI is
set -- see `smartmirror.content.enabled()`.
"""

import os
from pathlib import Path

COLLECTIONS = ("events", "announcements", "about", "achievements", "board")

DEFAULT_MONGO_URI = "mongodb://localhost:27017/ieee?directConnection=true"
DEFAULT_MONGO_DB = "ieee"
DEFAULT_QDRANT_COLLECTION = "ieee_content"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".cache"
DEFAULT_HEARTBEAT_INTERVAL = 30.0
DEFAULT_TIMEZONE = "Africa/Tunis"
DEFAULT_MIRROR_ID = "mirror-1"


class ContentSyncConfig:
    """Snapshot of env-derived settings. Construct once per process via `load_config()`."""

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.mongo_db = os.getenv("MONGO_DB", DEFAULT_MONGO_DB)
        self.cache_dir = Path(os.getenv("SMARTMIRROR_CONTENT_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
        self.qdrant_collection = os.getenv("SMARTMIRROR_CONTENT_QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION)
        self.qdrant_path = os.getenv("SMARTMIRROR_CONTENT_QDRANT_PATH")  # None -> VectorStore default
        self.mirror_id = os.getenv("SMARTMIRROR_MIRROR_ID", DEFAULT_MIRROR_ID)
        self.heartbeat_interval = float(os.getenv("SMARTMIRROR_CONTENT_HEARTBEAT_INTERVAL", DEFAULT_HEARTBEAT_INTERVAL))
        self.timezone = os.getenv("SMARTMIRROR_CONTENT_TIMEZONE", DEFAULT_TIMEZONE)

    @property
    def enabled(self) -> bool:
        return bool(self.mongo_uri)


def load_config() -> ContentSyncConfig:
    return ContentSyncConfig()


def enabled() -> bool:
    """True iff MONGO_URI is set -- the single on/off switch for the whole feature."""
    return bool(os.getenv("MONGO_URI"))
