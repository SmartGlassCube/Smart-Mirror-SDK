"""Integration tests against a real local Mongo (see conftest.requires_mongo).

Run: ../Dashboard/dev.sh up && uv run pytest smartmirror/content/tests -q
(Mongo is owned by the Dashboard repo now -- see MONGO_URI in this repo's .env)
"""
import threading
import time
from datetime import timedelta

from .conftest import make_about, make_announcement, make_event, requires_mongo, utcnow

pytestmark = requires_mongo


def _retrieve_sources(content_sync, query, top_k=10):
    from smartmirror.assistant.rag import Retriever
    retriever = Retriever(store=content_sync.indexer.store, embedder=content_sync.indexer.embedder, top_k=top_k)
    [query_embedding] = content_sync.indexer.embedder.embed(query)
    return {r["source"] for r in content_sync.indexer.store.query(query_embedding, top_k=top_k)}


def test_reconcile_inserts_appear_in_cache_and_qdrant(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Robotics Night")
    content_sync.reconcile()

    cached = content_sync.cache.docs("events")
    assert str(doc_id) in cached
    assert cached[str(doc_id)]["title"] == "Robotics Night"

    sources = _retrieve_sources(content_sync, "Robotics Night")
    assert f"events:{doc_id}" in sources


def test_reconcile_update_replaces_old_chunks(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Original Title", description="Original description about lasers.")
    content_sync.reconcile()
    assert "Original" in str(content_sync.cache.docs("events")[str(doc_id)]["title"])

    mongo_db.events.update_one({"_id": doc_id}, {"$set": {
        "title": "Updated Title", "description": "Updated description about rockets.", "updated_at": utcnow(),
    }})
    content_sync.reconcile()

    cached = content_sync.cache.docs("events")[str(doc_id)]
    assert cached["title"] == "Updated Title"

    [query_embedding] = content_sync.indexer.embedder.embed("rockets")
    results = content_sync.indexer.store.query(query_embedding, top_k=5)
    matching = [r for r in results if r["source"] == f"events:{doc_id}"]
    assert matching, "updated chunk not found"
    assert "rockets" in matching[0]["text"]
    assert "lasers" not in matching[0]["text"]


def test_reconcile_delete_removes_from_cache_and_qdrant(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Soon To Be Deleted")
    content_sync.reconcile()
    assert str(doc_id) in content_sync.cache.docs("events")

    mongo_db.events.delete_one({"_id": doc_id})
    content_sync.reconcile()

    assert str(doc_id) not in content_sync.cache.docs("events")
    sources = _retrieve_sources(content_sync, "Soon To Be Deleted")
    assert f"events:{doc_id}" not in sources


def test_reconcile_published_to_draft_removed(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Flip Flopper")
    content_sync.reconcile()
    assert str(doc_id) in content_sync.cache.docs("events")

    mongo_db.events.update_one({"_id": doc_id}, {"$set": {"status": "draft", "updated_at": utcnow()}})
    content_sync.reconcile()

    assert str(doc_id) not in content_sync.cache.docs("events")
    sources = _retrieve_sources(content_sync, "Flip Flopper")
    assert f"events:{doc_id}" not in sources


def test_reconcile_draft_never_indexed(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Never Published", status="draft")
    content_sync.reconcile()

    assert str(doc_id) not in content_sync.cache.docs("events")
    sources = _retrieve_sources(content_sync, "Never Published")
    assert f"events:{doc_id}" not in sources


def test_expired_announcement_not_in_widget_but_in_qdrant(mongo_db, content_sync):
    doc_id = make_announcement(
        mongo_db, title="Old News", body="This announcement has expired.",
        publish_at=utcnow() - timedelta(days=30), expires_at=utcnow() - timedelta(days=10),
    )
    content_sync.reconcile()

    widget_titles = [a["title"] for a in content_sync.widget_data("announcements")]
    assert "Old News" not in widget_titles

    sources = _retrieve_sources(content_sync, "Old News")
    assert f"announcements:{doc_id}" in sources


def test_past_event_not_in_widget_but_in_qdrant(mongo_db, content_sync):
    doc_id = make_event(mongo_db, title="Historical Assembly", start=utcnow() - timedelta(days=100))
    content_sync.reconcile()

    widget_titles = [e["title"] for e in content_sync.widget_data("events")]
    assert "Historical Assembly" not in widget_titles

    sources = _retrieve_sources(content_sync, "Historical Assembly")
    assert f"events:{doc_id}" in sources


def test_offline_gap_reconcile_catches_up(mongo_db, content_sync):
    """Simulates: watcher stopped, docs changed while offline, mirror restarts -> reconcile catches up."""
    doc_id = make_event(mongo_db, title="Before Gap")
    content_sync.reconcile()
    assert str(doc_id) in content_sync.cache.docs("events")

    # "offline": no watch() running. Mutate Mongo directly.
    mongo_db.events.delete_one({"_id": doc_id})
    new_id = make_event(mongo_db, title="Created While Offline")

    # "restart": fresh reconcile catches both changes.
    content_sync.reconcile()
    cached = content_sync.cache.docs("events")
    assert str(doc_id) not in cached
    assert str(new_id) in cached
    assert cached[str(new_id)]["title"] == "Created While Offline"


def test_invalid_resume_token_triggers_reconcile(mongo_db, content_sync):
    make_event(mongo_db, title="Seed Before Bad Token")
    content_sync.reconcile()
    assert len(content_sync.cache.docs("events")) == 1

    content_sync.cache.set_resume_token({"_data": "00" * 40})  # well-formed-looking but bogus/stale

    stop_event = threading.Event()
    watch_thread = threading.Thread(target=content_sync.watch, args=(stop_event,), daemon=True)
    watch_thread.start()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and content_sync.last_sync_at is None:
            time.sleep(0.2)
        assert content_sync.last_sync_at is not None, "watch() never reconciled after an invalid resume token"
    finally:
        stop_event.set()
        watch_thread.join(timeout=5)


def test_watch_observes_insert_update_delete(mongo_db, content_sync):
    content_sync.reconcile()

    stop_event = threading.Event()
    watch_thread = threading.Thread(target=content_sync.watch, args=(stop_event,), daemon=True)
    watch_thread.start()
    try:
        time.sleep(1)  # let the change stream subscribe before we write
        doc_id = make_event(mongo_db, title="Live Inserted")

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and str(doc_id) not in content_sync.cache.docs("events"):
            time.sleep(0.2)
        assert str(doc_id) in content_sync.cache.docs("events"), "insert not observed by watch()"

        mongo_db.events.delete_one({"_id": doc_id})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and str(doc_id) in content_sync.cache.docs("events"):
            time.sleep(0.2)
        assert str(doc_id) not in content_sync.cache.docs("events"), "delete not observed by watch()"
    finally:
        stop_event.set()
        watch_thread.join(timeout=5)


def test_embedding_model_mismatch_triggers_full_rebuild(mongo_db, content_sync):
    make_event(mongo_db, title="Rebuild Me")
    content_sync.reconcile()
    sidecar = content_sync.config.cache_dir / "embedding_model.json"
    assert sidecar.exists()

    import json
    stale = json.loads(sidecar.read_text())
    stale["model"] = "a-different-model"
    sidecar.write_text(json.dumps(stale))

    # Simulate boot with the real (unchanged) embedder but a stale sidecar: should rebuild, not crash.
    content_sync.reconcile()
    current = json.loads(sidecar.read_text())
    assert current["model"] == content_sync.indexer.embedder.model_name


def test_template_version_change_triggers_full_rebuild(mongo_db, content_sync, monkeypatch):
    from smartmirror.content import templates

    make_event(mongo_db, title="Re-render Me")
    content_sync.reconcile()
    upserted = []
    monkeypatch.setattr(content_sync.indexer, "upsert", lambda collection, doc: upserted.append(doc["title"]))

    content_sync.reconcile()  # nothing changed: nothing re-indexed
    assert upserted == []

    monkeypatch.setattr(templates, "TEMPLATE_VERSION", templates.TEMPLATE_VERSION + 1)
    content_sync.reconcile()  # unchanged doc, new templates: re-indexed
    assert "Re-render Me" in upserted


def test_heartbeat_upserts_mirror_status(mongo_db, content_sync):
    content_sync.heartbeat(current_page="home")
    doc = mongo_db.mirror_status.find_one({"mirror_id": content_sync.config.mirror_id})
    assert doc is not None
    assert doc["current_page"] == "home"
    assert doc["last_seen"] is not None


def test_prompt_block_assembles_from_cache(mongo_db, content_sync):
    make_event(mongo_db, title="Prompt Event")
    make_announcement(mongo_db, title="Prompt Announcement")
    make_about(mongo_db)
    content_sync.reconcile()

    block = content_sync.prompt_block()
    assert "Prompt Event" in block
    assert "Prompt Announcement" in block
    assert "Test mission body." in block


def test_mongo_down_does_not_raise(cache_dir, qdrant_collection, shared_embedder, tmp_path):
    from smartmirror.assistant.rag import VectorStore
    from smartmirror.content.cache import ContentCache
    from smartmirror.content.config import ContentSyncConfig
    from smartmirror.content.indexer import ContentIndexer
    from smartmirror.content.sync import ContentSync

    config = ContentSyncConfig()
    config.mongo_uri = "mongodb://127.0.0.1:1/?directConnection=true&serverSelectionTimeoutMS=200"
    config.mongo_db = "doesnotmatter"
    config.cache_dir = cache_dir

    cache = ContentCache(cache_dir)
    store = VectorStore(path=str(tmp_path / "qdrant"), collection_name=qdrant_collection)
    indexer = ContentIndexer(store=store, embedder=shared_embedder)
    sync = ContentSync(config, cache, indexer)

    sync.reconcile()  # must not raise
    assert sync.last_error is not None
    sync.client.close()


def test_contract_version_match_or_missing_allows_sync(mongo_db, content_sync):
    from smartmirror.content.config import CONTRACT_VERSION

    # No _meta doc at all (the conftest's lightweight schema doesn't create one).
    assert content_sync.check_contract_version() is True

    mongo_db["_meta"].update_one({"_id": "contract"}, {"$set": {"version": CONTRACT_VERSION}}, upsert=True)
    assert content_sync.check_contract_version() is True

    make_event(mongo_db, title="Should Sync Fine")
    content_sync.reconcile()
    assert len(content_sync.cache.docs("events")) == 1
    assert content_sync.last_error is None


def test_contract_version_major_mismatch_refuses_to_sync(mongo_db, content_sync):
    from smartmirror.content.config import CONTRACT_VERSION

    fake_major = str(int(CONTRACT_VERSION.split(".", 1)[0]) + 1)
    mongo_db["_meta"].update_one(
        {"_id": "contract"}, {"$set": {"version": f"{fake_major}.0"}}, upsert=True
    )

    make_event(mongo_db, title="Should Not Sync")
    assert content_sync.check_contract_version() is False
    assert "contract version mismatch" in content_sync.last_error

    content_sync.reconcile()
    assert content_sync.cache.docs("events") == {}  # refused -- cache untouched
    assert content_sync.last_sync_at is None

    # Restore -- subsequent reconcile proceeds normally.
    mongo_db["_meta"].update_one({"_id": "contract"}, {"$set": {"version": CONTRACT_VERSION}}, upsert=True)
    content_sync.reconcile()
    assert len(content_sync.cache.docs("events")) == 1
    assert content_sync.last_error is None


def test_contract_version_minor_difference_is_compatible(mongo_db, content_sync):
    from smartmirror.content.config import CONTRACT_VERSION

    major, minor = CONTRACT_VERSION.split(".", 1)
    other_minor = f"{major}.{int(minor) + 1}"
    mongo_db["_meta"].update_one({"_id": "contract"}, {"$set": {"version": other_minor}}, upsert=True)

    assert content_sync.check_contract_version() is True


def test_renaming_a_chapter_reindexes_its_content(mongo_db, content_sync, monkeypatch):
    from .conftest import make_chapter

    chapter_id = make_chapter(mongo_db)
    make_event(mongo_db, title="CS Workshop", chapter="cs")
    make_event(mongo_db, title="SB Assembly")
    content_sync.reconcile()
    assert "Computer Society chapter event: CS Workshop" in str(content_sync.indexer.store.query(
        content_sync.indexer.embedder.embed(["CS Workshop"])[0], top_k=5))

    reindexed = []
    real_upsert = content_sync.indexer.upsert
    monkeypatch.setattr(content_sync.indexer, "upsert",
                        lambda collection, doc: reindexed.append(doc.get("title") or doc.get("name")) or real_upsert(collection, doc))
    mongo_db.chapters.update_one({"_id": chapter_id}, {"$set": {"name": "IEEE CS", "updated_at": utcnow()}})
    content_sync.reconcile()

    assert sorted(reindexed) == ["CS Workshop", "IEEE CS"]  # the SB's own event untouched
    assert "IEEE CS chapter event: CS Workshop" in str(content_sync.indexer.store.query(
        content_sync.indexer.embedder.embed(["CS Workshop"])[0], top_k=5))


def test_reconcile_prints_the_content_that_came_from_the_dashboard(mongo_db, content_sync, caplog):
    from .conftest import make_chapter

    make_chapter(mongo_db)
    make_event(mongo_db, title="CS Workshop", chapter="cs", location="Lab 3")
    make_event(mongo_db, title="Draft Event", status="draft")

    with caplog.at_level("INFO", logger="smartmirror.content.sync"):
        content_sync.reconcile()

    dump = next(m for m in caplog.messages if m.startswith("Content from the dashboard"))
    assert "cs: Computer Society" in dump
    assert "[Computer Society] CS Workshop @ Lab 3" in dump
    assert "Draft Event" not in dump
    assert "calendar (1 days with events)" in dump


def _upload_image(mongo_db, data=b"\x89PNG fake", content_type="image/png"):
    from gridfs import GridFSBucket

    return str(GridFSBucket(mongo_db, bucket_name="images").upload_from_stream(
        "poster.png", data, metadata={"contentType": content_type, "uploaded_by": "test"},
    ))


def test_event_images_are_copied_from_gridfs_and_dropped_when_unused(mongo_db, content_sync):
    image_id = _upload_image(mongo_db)
    event_id = make_event(mongo_db, title="With Poster", image_id=image_id)
    make_event(mongo_db, title="No Poster")
    content_sync.reconcile()

    copy = content_sync.images_dir / f"{image_id}.png"
    assert copy.read_bytes() == b"\x89PNG fake"

    content_sync.image_base_url = "http://localhost:8080/content-images"
    cards = {card["name"]: card for card in content_sync.event_cards()}
    assert cards["With Poster"]["image"] == f"http://localhost:8080/content-images/{image_id}.png"
    assert cards["No Poster"]["image"] is None

    mongo_db.events.update_one({"_id": event_id}, {"$unset": {"image_id": ""}, "$set": {"updated_at": utcnow()}})
    content_sync.reconcile()
    assert not copy.exists()


def test_missing_gridfs_image_falls_back_to_the_placeholder(mongo_db, content_sync):
    from bson import ObjectId

    make_event(mongo_db, title="Lost Poster", image_id=str(ObjectId()))
    content_sync.reconcile()
    content_sync.image_base_url = "http://localhost:8080/content-images"

    assert content_sync.event_cards()[0]["image"] is None
