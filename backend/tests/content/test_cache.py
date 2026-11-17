from datetime import datetime, timezone

from glasscube.content.cache import ContentCache


def test_upsert_and_docs_roundtrip(tmp_path):
    cache = ContentCache(tmp_path)
    doc = {"title": "Event", "start": datetime(2026, 5, 1, tzinfo=timezone.utc), "status": "published"}
    cache.upsert("events", "id1", doc)

    docs = cache.docs("events")
    assert docs["id1"]["title"] == "Event"
    assert docs["id1"]["start"] == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_remove_docid(tmp_path):
    cache = ContentCache(tmp_path)
    cache.upsert("events", "id1", {"title": "Event"})
    cache.remove("events", "id1")
    assert cache.docs("events") == {}


def test_persists_across_instances(tmp_path):
    cache = ContentCache(tmp_path)
    cache.upsert("about", "id1", {"key": "mission", "body": "hi"})

    reloaded = ContentCache(tmp_path)
    assert reloaded.docs("about")["id1"]["body"] == "hi"


def test_resume_token_roundtrip(tmp_path):
    cache = ContentCache(tmp_path)
    assert cache.get_resume_token() is None
    cache.set_resume_token({"_data": "abc123"})

    reloaded = ContentCache(tmp_path)
    assert reloaded.get_resume_token() == {"_data": "abc123"}


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    cache = ContentCache(tmp_path)
    cache.upsert("events", "id1", {"title": "x"})
    assert cache.path.exists()
    assert not cache.path.with_suffix(".json.tmp").exists()


def test_bulk_replace(tmp_path):
    cache = ContentCache(tmp_path)
    cache.upsert("events", "stale", {"title": "stale"})
    cache.bulk_replace("events", {"fresh": {"title": "fresh"}})
    assert set(cache.docs("events")) == {"fresh"}
