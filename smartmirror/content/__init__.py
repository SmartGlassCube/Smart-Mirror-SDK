"""Mirror-side sync of IEEE INSAT club content from MongoDB (source of truth)
into a local cache (for widgets + the assistant's prompt block) and a
Qdrant collection (for RAG retrieval).

Opt-in: everything here is inert unless the MONGO_URI env var is set --
see `config.enabled()`. With it unset, the mirror behaves exactly as before
(the assistant's seed corpus, no club-content widgets).
"""

from .cache import ContentCache
from .config import ContentSyncConfig, enabled, load_config
from .indexer import ContentIndexer
from .sync import ContentSync, build_content_sync

__all__ = [
    "ContentCache",
    "ContentSyncConfig",
    "ContentIndexer",
    "ContentSync",
    "build_content_sync",
    "enabled",
    "load_config",
]
