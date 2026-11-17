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
import mimetypes
import os
import threading
import time
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import GridFSBucket, NoFile
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from .cache import ContentCache
from .config import CHAPTERED_COLLECTIONS, COLLECTIONS, CONTRACT_VERSION, IMAGES_BUCKET, ContentSyncConfig
from .indexer import ContentIndexer, source_id
from . import routing, templates

logger = logging.getLogger(__name__)

# ChangeStreamHistoryLost -- the resume token is too old/invalid; the only
# fix is a full reconcile and a fresh stream.
_RESUME_TOKEN_INVALID_CODE = 286


def _is_resume_token_invalid(error: OperationFailure) -> bool:
    return error.code == _RESUME_TOKEN_INVALID_CODE or "resume" in str(error).lower()


def _updated_at(doc: dict):
    return doc.get("updated_at")


def _major(version: str) -> str:
    return version.split(".", 1)[0]


class ContentSync:
    """Owns the Mongo connection, the on-disk cache, and the Qdrant indexer."""

    def __init__(self, config: ContentSyncConfig, cache: ContentCache, indexer: ContentIndexer):
        self.config = config
        self.cache = cache
        self.indexer = indexer
        # Indexed text names a doc's chapter, from the cached chapters.
        self.indexer.chapters = self.chapter_names
        # Local copies of the events' uploaded images (GridFS), served by the mirror's
        # server; it sets image_base_url to where (see SmartMirrorServer).
        self.images_dir = config.cache_dir / "images"
        self.image_base_url = None
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

    def chapter_names(self) -> dict:
        """{key: name} of the published chapters."""
        return routing.chapter_names(list(self.cache.docs("chapters").values()))

    def calendar_days(self) -> dict:
        """Every event keyed by local day, for the calendar widget: {"2026-10-28": [event, ...]}."""
        return routing.events_by_day(list(self.cache.docs("events").values()), self.chapter_names())

    def event_cards(self, now: datetime = None) -> list[dict]:
        """Every event, upcoming then past, for the events page."""
        return routing.event_cards(list(self.cache.docs("events").values()), self.chapter_names(), now, self.image_urls())

    def image_urls(self) -> dict:
        """{image_id: URL} of the images copied locally, once the server says where it serves them."""
        if self.image_base_url is None or not self.images_dir.exists():
            return {}
        return {path.stem: f"{self.image_base_url}/{path.name}" for path in self.images_dir.iterdir() if path.is_file()}

    def sync_images(self) -> None:
        """Copy the cached events' uploaded images from GridFS, and drop the ones no event uses anymore."""
        wanted = {doc["image_id"] for doc in self.cache.docs("events").values() if doc.get("image_id")}
        self.images_dir.mkdir(parents=True, exist_ok=True)
        have = {path.stem: path for path in self.images_dir.iterdir() if path.is_file()}
        for image_id, path in have.items():
            if image_id not in wanted:
                path.unlink(missing_ok=True)
        bucket = GridFSBucket(self.db, bucket_name=IMAGES_BUCKET)
        for image_id in wanted - have.keys():
            try:
                stream = bucket.open_download_stream(ObjectId(image_id))
            except (InvalidId, NoFile):
                logger.warning("event image %s not found in GridFS -- the event shows the placeholder", image_id)
                continue
            content_type = (stream.metadata or {}).get("contentType", "")
            extension = mimetypes.guess_extension(content_type) or ".img"
            tmp_path = self.images_dir / f".{image_id}.tmp"
            tmp_path.write_bytes(stream.read())
            os.replace(tmp_path, self.images_dir / f"{image_id}{extension}")
            logger.info("copied event image %s (%s) from the dashboard", image_id, content_type)

    def news(self, now: datetime = None) -> list[dict]:
        """Active announcements, then achievements, for the news widget."""
        return routing.news_items(
            list(self.cache.docs("announcements").values()),
            list(self.cache.docs("achievements").values()),
            self.chapter_names(),
            now,
        )

    def prompt_block(self, now: datetime = None) -> str:
        return routing.build_prompt_block(
            list(self.cache.docs("events").values()),
            list(self.cache.docs("announcements").values()),
            list(self.cache.docs("about").values()),
            now,
            chapter_docs=list(self.cache.docs("chapters").values()),
        )

    def log_content(self) -> None:
        """Print everything the mirror got from the dashboard (published only), to debug the sync."""
        lines = ["Content from the dashboard (published only):"]
        chapters = self.chapter_names()
        for collection in COLLECTIONS:
            docs = sorted(self.cache.docs(collection).values(), key=lambda doc: _describe(collection, doc, chapters))
            lines.append(f"  {collection} ({len(docs)}):")
            lines += [f"    - {_describe(collection, doc, chapters)}" for doc in docs]
        days = self.calendar_days()
        lines.append(f"  calendar ({len(days)} days with events):")
        lines += [f"    - {day}: {', '.join(event['title'] for event in events)}" for day, events in sorted(days.items())]
        logger.info("\n".join(lines))

    def _reindex_chapter_content(self, names_before: dict) -> None:
        """Re-index the content of every chapter added, renamed, or removed since `names_before`."""
        names_after = self.chapter_names()
        changed = {key for key in names_before.keys() | names_after.keys() if names_before.get(key) != names_after.get(key)}
        if not changed:
            return
        logger.info("chapters changed (%s): re-indexing their content", ", ".join(sorted(changed)))
        for collection in CHAPTERED_COLLECTIONS:
            for doc in self.cache.docs(collection).values():
                if doc.get("chapter") in changed:
                    self.indexer.upsert(collection, doc)

    # -- contract version: refuse to sync against an incompatible Dashboard --

    def check_contract_version(self) -> bool:
        """False only if Mongo is reachable AND reports an incompatible major
        contract version (infra/mongo/CONTRACT.md, owned by the Dashboard
        repo) -- Mongo being unreachable is left for reconcile()/watch()'s
        own retry logic to handle, not treated as incompatible here.
        """
        try:
            doc = self.db["_meta"].find_one({"_id": "contract"})
        except PyMongoError:
            return True
        if doc is None or "version" not in doc:
            return True  # no _meta yet (older Dashboard, or a dev DB seeded by hand) -- assume compatible
        mongo_version = doc["version"]
        if _major(mongo_version) != _major(CONTRACT_VERSION):
            logger.error(
                "contract version mismatch: Mongo reports v%s, this code expects v%s "
                "(major version differs) -- refusing to sync until this is fixed.",
                mongo_version, CONTRACT_VERSION,
            )
            self.last_error = f"contract version mismatch: Mongo v{mongo_version} vs code v{CONTRACT_VERSION}"
            return False
        return True

    # -- reconcile: full diff, safe to call any time (boot, or resume-token loss) --

    def reconcile(self) -> None:
        if not self.check_contract_version():
            return
        try:
            force_reindex = self._check_embedding_model()
            chapters_before = self.chapter_names()
            for collection in COLLECTIONS:
                self._reconcile_collection(collection, force_reindex)
            if not force_reindex:
                self._reindex_chapter_content(chapters_before)
            self.sync_images()
            self.last_sync_at = datetime.now(timezone.utc)
            self.last_error = None
            logger.info("reconcile complete")
            self.log_content()
        except PyMongoError as error:
            logger.warning("reconcile failed (Mongo unreachable?): %s", error)
            self.last_error = str(error)

    def _check_embedding_model(self) -> bool:
        """Return True (and wipe Qdrant) if the embedding model/collection or the text templates changed since last boot."""
        sidecar = self.config.cache_dir / "embedding_model.json"
        current = {
            "model": self.indexer.embedder.model_name,
            "collection": self.indexer.store.collection_name,
            "templates": templates.TEMPLATE_VERSION,
        }
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
        chapters_before = self.chapter_names()
        self._apply_change(collection, change)
        if collection == "chapters":
            self._reindex_chapter_content(chapters_before)
        if collection == "events":
            self.sync_images()

    def _apply_change(self, collection: str, change: dict) -> None:

        if change["operationType"] == "delete":
            doc_id = str(change["documentKey"]["_id"])
            logger.info("dashboard change: deleted %s %s", collection, doc_id)
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
                logger.info("dashboard change: unpublished %s: %s", collection, _describe(collection, doc, self.chapter_names()))
                self.cache.remove(collection, doc_id)
                self.indexer.remove(source_id(collection, doc_id))
            return

        self.cache.upsert(collection, doc_id, doc)
        self.indexer.upsert(collection, doc)
        logger.info("dashboard change: %s %s: %s", change["operationType"], collection, _describe(collection, doc, self.chapter_names()))

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
        if not await asyncio.to_thread(self.check_contract_version):
            # Logged already. Don't reconcile or watch -- just keep
            # heartbeating so the dashboard can see this mirror is alive
            # and why it isn't syncing (last_error).
            await self._heartbeat_loop(current_page_getter, stop_event)
            return
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


def _describe(collection: str, doc: dict, chapters: dict) -> str:
    """One line per doc for log_content: the date (if any), whose it is, and what it is."""
    owner = f"[{templates.chapter_name(doc, chapters) or 'SB'}]"
    if collection == "chapters":
        return f"{doc['key']}: {doc['name']}"
    if collection == "events":
        where = f" @ {doc['location']}" if doc.get("location") else ""
        image = f" (image {doc['image_id']})" if doc.get("image_id") else ""
        return f"{templates.to_local(doc['start']):%Y-%m-%d %H:%M} {owner} {doc['title']}{where}{image}"
    if collection == "announcements":
        until = f" -> {templates.to_local(doc['expires_at']):%Y-%m-%d}" if doc.get("expires_at") else ""
        return f"{templates.to_local(doc['publish_at']):%Y-%m-%d}{until} {owner} ({doc.get('priority', 'normal')}) {doc['title']}"
    if collection == "about":
        return f"{doc['key']}: {doc['title']}"
    if collection == "achievements":
        return f"{templates.to_local(doc['date']):%Y-%m-%d} {owner} {doc['title']}"
    if collection == "board":
        return f"{owner} {doc['role']}: {doc['name']} ({doc['term']})"
    return str(doc.get("_id"))


def build_content_sync(config: ContentSyncConfig = None) -> ContentSync:
    """Construct a ready-to-use ContentSync from env config: cache loaded, indexer wired to its own Qdrant collection."""
    from glasscube.assistant.rag import Embedder, VectorStore

    from .config import load_config

    config = config or load_config()
    cache = ContentCache(config.cache_dir)
    store_kwargs = {"collection_name": config.qdrant_collection}
    if config.qdrant_path:
        store_kwargs["path"] = config.qdrant_path
    store = VectorStore(**store_kwargs)
    indexer = ContentIndexer(store=store, embedder=Embedder())
    return ContentSync(config, cache, indexer)
