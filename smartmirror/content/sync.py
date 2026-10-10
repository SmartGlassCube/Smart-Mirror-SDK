"""Keeps the mirror's cache + Qdrant index in sync with Mongo.

Boot order (see ContentSync.run_forever): the cache is loaded synchronously
in __init__, so widget_data()/prompt_block() work immediately -- even before
Mongo has been reached. reconcile() then does a full diff, and watch() takes
over with a change stream. Mongo being unreachable at any point is caught
and logged, never raised past this module -- the mirror keeps running on
whatever the cache already has.
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from .cache import ContentCache
from .config import COLLECTIONS, ContentSyncConfig
from .indexer import ContentIndexer, source_id
from . import routing

logger = logging.getLogger(__name__)

# ChangeStreamHistoryLost -- the resume token is too old/invalid; the only
# fix is a full reconcile and a fresh stream.
_RESUME_TOKEN_INVALID_CODE = 286


def _is_resume_token_invalid(error: OperationFailure) -> bool:
    return error.code == _RESUME_TOKEN_INVALID_CODE or "resume" in str(error).lower()


def _updated_at(doc: dict):
    return doc.get("updated_at")


class ContentSync:
    """Owns the Mongo connection, the on-disk cache, and the Qdrant indexer."""

    def __init__(self, config: ContentSyncConfig, cache: ContentCache, indexer: ContentIndexer):
        self.config = config
        self.cache = cache
        self.indexer = indexer
        self.client = MongoClient(config.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
        self.db = self.client[config.mongo_db]

        self.last_sync_at = None
        self.last_error = None
        self._start_time = time.monotonic()

    # -- data for widgets / the assistant's prompt, always served from cache --

    def widget_data(self, collection: str, now: datetime = None) -> list[dict]:
        docs = list(self.cache.docs(collection).values())
        if collection == "events":
            return routing.upcoming_events(docs, now)
        if collection == "announcements":
            return routing.active_announcements(docs, now)
        return [doc for doc in docs if routing.is_published(doc)]

    def prompt_block(self, now: datetime = None) -> str:
        return routing.build_prompt_block(
            list(self.cache.docs("events").values()),
            list(self.cache.docs("announcements").values()),
            list(self.cache.docs("about").values()),
            now,
        )

    # -- reconcile: full diff, safe to call any time (boot, or resume-token loss) --

    def reconcile(self) -> None:
        try:
            force_reindex = self._check_embedding_model()
            for collection in COLLECTIONS:
                self._reconcile_collection(collection, force_reindex)
            self.last_sync_at = datetime.now(timezone.utc)
            self.last_error = None
            logger.info("reconcile complete")
        except PyMongoError as error:
            logger.warning("reconcile failed (Mongo unreachable?): %s", error)
            self.last_error = str(error)

    def _check_embedding_model(self) -> bool:
        """Return True (and wipe Qdrant) if the embedding model/collection changed since last boot."""
        sidecar = self.config.cache_dir / "embedding_model.json"
        current = {"model": self.indexer.embedder.model_name, "collection": self.indexer.store.collection_name}
        stored = None
        if sidecar.exists():
            try:
                stored = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = None
        if stored == current:
            return False
        logger.warning("embedding model/collection changed (%s -> %s); rebuilding Qdrant index", stored, current)
        self.indexer.store.clear()
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(current), encoding="utf-8")
        return True

    def _reconcile_collection(self, collection: str, force_reindex: bool) -> None:
        mongo_docs = {str(doc["_id"]): doc for doc in self.db[collection].find({"status": "published"})}
        cached_docs = self.cache.docs(collection)

        for doc_id, doc in mongo_docs.items():
            cached_doc = cached_docs.get(doc_id)
            changed = cached_doc is None or _updated_at(cached_doc) != _updated_at(doc)
            if changed:
                self.cache.upsert(collection, doc_id, doc)
            if changed or force_reindex:
                self.indexer.upsert(collection, doc)

        for doc_id in set(cached_docs) - set(mongo_docs):
            self.cache.remove(collection, doc_id)
            self.indexer.remove(source_id(collection, doc_id))

    # -- watch: change stream, persists the resume token after every event --

    def watch(self, stop_event: threading.Event = None) -> None:
        """Blocking. Run via asyncio.to_thread; set `stop_event` to make it return."""
        backoff = 1.0
        while stop_event is None or not stop_event.is_set():
            try:
                self._watch_once(stop_event)
                backoff = 1.0
                continue
            except OperationFailure as error:
                if _is_resume_token_invalid(error):
                    logger.warning("resume token invalid, reconciling before resubscribing: %s", error)
                    self.cache.set_resume_token(None)
                    self.reconcile()
                else:
                    logger.warning("change stream error: %s", error)
                    self.last_error = str(error)
            except PyMongoError as error:
                logger.warning("change stream connection lost: %s", error)
                self.last_error = str(error)

            if stop_event is not None and stop_event.wait(backoff):
                break
            backoff = min(backoff * 2, 30.0)

    def _watch_once(self, stop_event: threading.Event) -> None:
        resume_token = self.cache.get_resume_token()
        kwargs = {"full_document": "updateLookup"}
        if resume_token:
            kwargs["resume_after"] = resume_token
        with self.db.watch(**kwargs) as stream:
            while stop_event is None or not stop_event.is_set():
                change = stream.try_next()
                if change is None:
                    if stop_event is not None and stop_event.wait(0.5):
                        return
                    continue
                self._handle_change(change)
                self.cache.set_resume_token(stream.resume_token)

    def _handle_change(self, change: dict) -> None:
        collection = change["ns"]["coll"]
        if collection not in COLLECTIONS:
            return

        if change["operationType"] == "delete":
            doc_id = str(change["documentKey"]["_id"])
            self.cache.remove(collection, doc_id)
            self.indexer.remove(source_id(collection, doc_id))
            return

        doc = change.get("fullDocument")
        if doc is None:
            return
        doc_id = str(doc["_id"])

        if not routing.is_published(doc):
            # published -> draft (or never published): must not be in the cache/index.
            if doc_id in self.cache.docs(collection):
                self.cache.remove(collection, doc_id)
                self.indexer.remove(source_id(collection, doc_id))
            return

        self.cache.upsert(collection, doc_id, doc)
        self.indexer.upsert(collection, doc)

    # -- heartbeat --

    def heartbeat(self, current_page: str = None) -> None:
        now = datetime.now(timezone.utc)
        try:
            self.db.mirror_status.update_one(
                {"mirror_id": self.config.mirror_id},
                {"$set": {
                    "mirror_id": self.config.mirror_id,
                    "last_seen": now,
                    "uptime_s": time.monotonic() - self._start_time,
                    "current_page": current_page,
                    "last_sync_at": self.last_sync_at,
                    "last_error": self.last_error,
                    "updated_at": now,
                }},
                upsert=True,
            )
        except PyMongoError as error:
            logger.warning("heartbeat failed: %s", error)
            self.last_error = str(error)

    # -- async wiring for the server --

    async def run_forever(self, current_page_getter=None, stop_event: threading.Event = None) -> None:
        """Reconcile once, then watch() and heartbeat forever, side by side.

        Blocking pymongo work runs in a thread executor so it never stalls
        the event loop -- plug this in alongside camera_loop via
        asyncio.gather, same pattern as Assistant.listen_loop.
        """
        stop_event = stop_event or threading.Event()
        await asyncio.to_thread(self.reconcile)
        await asyncio.gather(
            asyncio.to_thread(self.watch, stop_event),
            self._heartbeat_loop(current_page_getter, stop_event),
        )

    async def _heartbeat_loop(self, current_page_getter, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            page = current_page_getter() if current_page_getter else None
            await asyncio.to_thread(self.heartbeat, page)
            await self._sleep_or_stop(self.config.heartbeat_interval, stop_event)

    @staticmethod
    async def _sleep_or_stop(seconds: float, stop_event: threading.Event) -> None:
        """asyncio.sleep(seconds), but wakes up early (in <=0.5s steps) once stop_event is set."""
        deadline = time.monotonic() + seconds
        while not stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(0.5, remaining))


def build_content_sync(config: ContentSyncConfig = None) -> ContentSync:
    """Construct a ready-to-use ContentSync from env config: cache loaded, indexer wired to its own Qdrant collection."""
    from smartmirror.assistant.rag import Embedder, VectorStore

    from .config import load_config

    config = config or load_config()
    cache = ContentCache(config.cache_dir)
    store_kwargs = {"collection_name": config.qdrant_collection}
    if config.qdrant_path:
        store_kwargs["path"] = config.qdrant_path
    store = VectorStore(**store_kwargs)
    indexer = ContentIndexer(store=store, embedder=Embedder())
    return ContentSync(config, cache, indexer)
