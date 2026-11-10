"""Local on-disk cache of published Mongo docs, plus the change-stream resume token.

Lets the mirror serve widgets/prompt-block data immediately on boot, before
Mongo has even been reached (reconcile runs after the cache loads). A single
JSON file, written atomically (write to a .tmp file, then os.replace) so a
crash mid-write never corrupts it.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import COLLECTIONS

# Contract fields that are BSON Date in Mongo; JSON can't carry datetime, so
# these are the only field names round-tripped to/from ISO-8601 strings.
_DATE_FIELDS = {"start", "end", "publish_at", "expires_at", "created_at", "updated_at", "date"}

CACHE_FILENAME = "cache.json"


def _serialize_doc(doc: dict) -> dict:
    out = {}
    for key, value in doc.items():
        if key == "_id":
            out[key] = str(value)
        elif key in _DATE_FIELDS and isinstance(value, datetime):
            out[key] = value.astimezone(timezone.utc).isoformat()
        else:
            out[key] = value
    return out


def _deserialize_doc(doc: dict) -> dict:
    out = {}
    for key, value in doc.items():
        if key in _DATE_FIELDS and isinstance(value, str):
            out[key] = datetime.fromisoformat(value)
        else:
            out[key] = value
    return out


def _empty() -> dict:
    return {"resume_token": None, "collections": {c: {} for c in COLLECTIONS}}


class ContentCache:
    """id -> doc per collection, loaded from and flushed to `cache_dir/cache.json`."""

    def __init__(self, cache_dir: Path):
        self.path = Path(cache_dir) / CACHE_FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._read()

    def _read(self) -> dict:
        if not self.path.exists():
            return _empty()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty()
        raw.setdefault("resume_token", None)
        raw.setdefault("collections", {})
        for collection in COLLECTIONS:
            raw["collections"].setdefault(collection, {})
        return raw

    def _flush(self) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp_path, self.path)

    def docs(self, collection: str) -> dict:
        """{doc_id: doc} for `collection`, with date fields deserialized back to datetime."""
        return {doc_id: _deserialize_doc(doc) for doc_id, doc in self._data["collections"].get(collection, {}).items()}

    def upsert(self, collection: str, doc_id: str, doc: dict) -> None:
        self._data["collections"].setdefault(collection, {})[doc_id] = _serialize_doc(doc)
        self._flush()

    def remove(self, collection: str, doc_id: str) -> None:
        if self._data["collections"].get(collection, {}).pop(doc_id, None) is not None:
            self._flush()

    def bulk_replace(self, collection: str, docs_by_id: dict) -> None:
        """Replace the entire in-memory set for `collection`, one flush."""
        self._data["collections"][collection] = {doc_id: _serialize_doc(doc) for doc_id, doc in docs_by_id.items()}
        self._flush()

    def get_resume_token(self):
        return self._data.get("resume_token")

    def set_resume_token(self, token) -> None:
        self._data["resume_token"] = token
        self._flush()
