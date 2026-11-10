import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from smartmirror.assistant.rag import Embedder, VectorStore
from smartmirror.content.cache import ContentCache
from smartmirror.content.config import COLLECTIONS, ContentSyncConfig
from smartmirror.content.indexer import ContentIndexer
from smartmirror.content.sync import ContentSync

# Mongo is owned by the Dashboard repo (../Dashboard) -- these tests just
# need MONGO_URI (same var the content sync itself reads) to point at it.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/ieee?directConnection=true")
TEST_DB = "ieee_content_sync_test"

NOT_REACHABLE_MESSAGE = (
    f"Mongo not reachable at {MONGO_URI} -- it's owned by the Dashboard repo now, "
    "start it with ../Dashboard/dev.sh up (or set MONGO_URI to point at it)"
)


def _mongo_reachable() -> bool:
    try:
        MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000).admin.command("ping")
        return True
    except PyMongoError:
        return False


requires_mongo = pytest.mark.skipif(not _mongo_reachable(), reason=NOT_REACHABLE_MESSAGE)


@pytest.fixture
def mongo_db():
    """A clean, throwaway database (not `ieee`) with the same $jsonSchema validators as init_db.js."""
    client = MongoClient(MONGO_URI, tz_aware=True)
    db = client[TEST_DB]
    for name in client[TEST_DB].list_collection_names():
        db.drop_collection(name)

    str_schema = {"bsonType": "string", "minLength": 1}
    date_schema = {"bsonType": "date"}
    common = {
        "status": {"enum": ["draft", "published"]},
        "created_at": date_schema,
        "updated_at": date_schema,
        "updated_by": str_schema,
    }
    common_req = ["status", "created_at", "updated_at", "updated_by"]

    def ensure(name, props, required):
        db.create_collection(name, validator={"$jsonSchema": {
            "bsonType": "object",
            "required": common_req + required,
            "properties": {**common, **props},
        }}, validationLevel="strict", validationAction="error")

    ensure("chapters", {"key": str_schema, "name": str_schema, "description": str_schema},
           ["key", "name", "description"])
    ensure("events", {
        "title": str_schema, "description": str_schema, "start": date_schema, "end": date_schema,
        "location": {"bsonType": "string"},
    }, ["title", "description", "start"])
    ensure("announcements", {
        "title": str_schema, "body": str_schema, "publish_at": date_schema, "expires_at": date_schema,
        "priority": {"enum": ["low", "normal", "high"]},
    }, ["title", "body", "publish_at", "priority"])
    ensure("about", {"key": str_schema, "title": str_schema, "body": str_schema}, ["key", "title", "body"])
    ensure("achievements", {"title": str_schema, "date": date_schema, "description": str_schema},
           ["title", "date", "description"])
    ensure("board", {"name": str_schema, "role": str_schema, "term": str_schema, "order": {"bsonType": "int"}},
           ["name", "role", "term", "order"])

    yield db

    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def cache_dir(tmp_path):
    path = tmp_path / "content_cache"
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def qdrant_collection():
    """A unique Qdrant collection name per test, in the same on-disk store as the assistant (but isolated by name)."""
    return f"test_content_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def shared_embedder():
    # Loading the sentence-transformers model is slow; share one across the whole test session.
    return Embedder()


@pytest.fixture
def content_sync(mongo_db, cache_dir, qdrant_collection, shared_embedder, tmp_path):
    config = ContentSyncConfig()
    config.mongo_uri = MONGO_URI
    config.mongo_db = TEST_DB
    config.cache_dir = cache_dir
    config.qdrant_collection = qdrant_collection

    cache = ContentCache(cache_dir)
    store = VectorStore(path=str(tmp_path / "qdrant"), collection_name=qdrant_collection)
    indexer = ContentIndexer(store=store, embedder=shared_embedder)
    sync = ContentSync(config, cache, indexer)
    yield sync
    sync.client.close()


def utcnow():
    return datetime.now(timezone.utc)


def make_event(db, **overrides):
    now = utcnow()
    doc = {
        "status": "published", "created_at": now, "updated_at": now, "updated_by": "test",
        "title": "Test Event", "description": "A test event description.",
        "start": now + timedelta(days=5), "location": "INSAT",
    }
    doc.update(overrides)
    return db.events.insert_one(doc).inserted_id


def make_chapter(db, **overrides):
    now = utcnow()
    doc = {
        "status": "published", "created_at": now, "updated_at": now, "updated_by": "test",
        "key": "cs", "name": "Computer Society", "description": "Software and AI workshops.",
    }
    doc.update(overrides)
    return db.chapters.insert_one(doc).inserted_id


def make_announcement(db, **overrides):
    now = utcnow()
    doc = {
        "status": "published", "created_at": now, "updated_at": now, "updated_by": "test",
        "title": "Test Announcement", "body": "A test announcement body.",
        "publish_at": now - timedelta(days=1), "priority": "normal",
    }
    doc.update(overrides)
    return db.announcements.insert_one(doc).inserted_id


def make_about(db, **overrides):
    now = utcnow()
    doc = {
        "status": "published", "created_at": now, "updated_at": now, "updated_by": "test",
        "key": "mission", "title": "Mission", "body": "Test mission body.",
    }
    doc.update(overrides)
    return db.about.insert_one(doc).inserted_id
