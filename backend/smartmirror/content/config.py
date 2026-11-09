"""Configuration for the Mongo content sync, read from env vars with sane defaults.

The mirror runs exactly as today (seed corpus, no sync) unless MONGO_URI is
set -- see `smartmirror.content.enabled()`.

MONGO_URI is the *only* thing this package shares with the Dashboard repo
(https://github.com/SmartGlassCube/Dashboard), which owns the database and
infra/mongo/CONTRACT.md. No shared code, no API calls between the repos --
just that Mongo URI and the contract version below.
"""

import os
import re
from pathlib import Path

from ..config import data_dir

# chapters first: the other collections' docs name their chapter when indexed.
COLLECTIONS = ("chapters", "events", "announcements", "about", "achievements", "board")
# GridFS bucket holding the events' uploaded images (contract v0.6).
IMAGES_BUCKET = "images"
# Collections whose docs may belong to a chapter (contract v0.5); no `chapter` = the whole SB.
CHAPTERED_COLLECTIONS = ("events", "announcements", "achievements", "board")

# The contract version (infra/mongo/CONTRACT.md in the Dashboard repo) this
# code was built against. sync.py refuses to touch the cache/Qdrant if the
# Mongo it's talking to reports a different *major* version (the part
# before the first "."); a minor difference is treated as compatible.
CONTRACT_VERSION = "0.6"

DEFAULT_MONGO_URI = "mongodb://localhost:27017/ieee?directConnection=true"
DEFAULT_MONGO_DB = "ieee"
DEFAULT_QDRANT_COLLECTION = "ieee_content"
DEFAULT_HEARTBEAT_INTERVAL = 30.0
DEFAULT_TIMEZONE = "Africa/Tunis"
DEFAULT_MIRROR_ID = "mirror-1"


class ContentSyncConfig:
    """Snapshot of env-derived settings. Construct once per process via `load_config()`."""

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.mongo_db = os.getenv("MONGO_DB", DEFAULT_MONGO_DB)
        self.cache_dir = Path(os.getenv("SMARTMIRROR_CONTENT_CACHE_DIR") or data_dir("content-cache"))
        self.qdrant_collection = os.getenv("SMARTMIRROR_CONTENT_QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION)
        self.qdrant_path = os.getenv("SMARTMIRROR_CONTENT_QDRANT_PATH")  # None -> VectorStore default
        self.mirror_id = os.getenv("SMARTMIRROR_MIRROR_ID", DEFAULT_MIRROR_ID)
        self.heartbeat_interval = float(os.getenv("SMARTMIRROR_CONTENT_HEARTBEAT_INTERVAL", DEFAULT_HEARTBEAT_INTERVAL))
        self.timezone = os.getenv("SMARTMIRROR_CONTENT_TIMEZONE", DEFAULT_TIMEZONE)

    @property
    def enabled(self) -> bool:
        return bool(self.mongo_uri)

    @property
    def mongo_uri_redacted(self) -> str:
        """mongo_uri without its user:password@ part -- the only form that's safe to log."""
        return re.sub(r"(://)[^/?@]*@", r"\1", self.mongo_uri or "")


def load_config() -> ContentSyncConfig:
    return ContentSyncConfig()


def enabled() -> bool:
    """True iff MONGO_URI is set -- the single on/off switch for the whole feature."""
    return bool(os.getenv("MONGO_URI"))
