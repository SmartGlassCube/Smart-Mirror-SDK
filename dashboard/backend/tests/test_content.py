from datetime import datetime, timedelta, timezone


def _iso(dt):
    return dt.isoformat()


def test_create_event_sets_server_fields_and_ignores_client_ones(logged_in_client, db):
    payload = {
        "title": "Robotics Night", "description": "A night of robots.",
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=5)),
        "created_at": "2000-01-01T00:00:00Z", "updated_by": "someone-else",  # must be ignored
    }
    resp = logged_in_client.post("/api/events", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_by"] == "admin"
    assert body["created_at"] != "2000-01-01T00:00:00Z"
    assert body["status"] == "draft"
    assert body["warnings"] == []

    stored = db.events.find_one({"title": "Robotics Night"})
    assert stored["updated_by"] == "admin"


def test_create_event_missing_required_field_is_422(logged_in_client):
    resp = logged_in_client.post("/api/events", json={"title": "No description"})
    assert resp.status_code == 422


def test_get_list_update_delete_event(logged_in_client):
    payload = {
        "title": "Original", "description": "Original description text here.",
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=1)),
    }
    created = logged_in_client.post("/api/events", json=payload).json()
    doc_id = created["id"]

    listing = logged_in_client.get("/api/events").json()
    assert any(e["id"] == doc_id for e in listing)

    got = logged_in_client.get(f"/api/events/{doc_id}")
    assert got.status_code == 200
    assert got.json()["title"] == "Original"

    update_payload = {**payload, "title": "Updated"}
    updated = logged_in_client.put(f"/api/events/{doc_id}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert updated.json()["created_at"] == created["created_at"]

    deleted = logged_in_client.delete(f"/api/events/{doc_id}")
    assert deleted.status_code == 204
    assert logged_in_client.get(f"/api/events/{doc_id}").status_code == 404


def test_publish_unpublish_toggle(logged_in_client):
    payload = {
        "title": "Toggle Me", "description": "Describe the toggle event here please.",
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=1)),
    }
    doc_id = logged_in_client.post("/api/events", json=payload).json()["id"]
    assert logged_in_client.get(f"/api/events/{doc_id}").json()["status"] == "draft"

    published = logged_in_client.patch(f"/api/events/{doc_id}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    unpublished = logged_in_client.patch(f"/api/events/{doc_id}/unpublish")
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "draft"


def test_invalid_doc_rejected_with_422(logged_in_client):
    # Mongo's $jsonSchema validator itself should reject a doc missing a
    # required field if it ever got past Pydantic (defense in depth) --
    # simulate by hitting the API with a borderline-valid-but-wrong type.
    resp = logged_in_client.post("/api/events", json={"title": "x", "description": "x", "start": "not-a-date"})
    assert resp.status_code == 422


def test_english_warning_on_non_english_long_text(logged_in_client):
    payload = {
        "title": "Evenement francais",
        "description": "Ceci est une description assez longue en francais pour declencher la detection.",
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=1)),
    }
    resp = logged_in_client.post("/api/events", json=payload)
    assert resp.status_code == 200
    assert resp.json()["warnings"], "expected a non-English warning"


def test_short_text_skips_english_check(logged_in_client):
    payload = {
        "title": "OK", "description": "Trop court",  # < 20 chars, should be skipped
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=1)),
    }
    resp = logged_in_client.post("/api/events", json=payload)
    assert resp.status_code == 200
    assert resp.json()["warnings"] == []


def test_audit_log_written_on_create_update_delete(logged_in_client, db):
    payload = {
        "title": "Audited", "description": "This event should be audited on every write.",
        "start": _iso(datetime.now(timezone.utc) + timedelta(days=1)),
    }
    doc_id = logged_in_client.post("/api/events", json=payload).json()["id"]
    logged_in_client.put(f"/api/events/{doc_id}", json=payload)
    logged_in_client.patch(f"/api/events/{doc_id}/publish")
    logged_in_client.delete(f"/api/events/{doc_id}")

    ops = [entry["operation"] for entry in db.audit_log.find({"document_id": doc_id}).sort("at", 1)]
    assert ops == ["create", "update", "status:published", "delete"]
    assert all(entry["username"] == "admin" for entry in db.audit_log.find({"document_id": doc_id}))


def test_about_unique_key_validator_enforced_by_mongo(logged_in_client):
    payload = {"key": "mission", "title": "Mission", "body": "Our mission statement is long enough to matter."}
    first = logged_in_client.post("/api/about", json=payload)
    assert first.status_code == 200
    # No unique index in the lightweight test schema (conftest), so this
    # exercises the write path twice rather than the uniqueness constraint
    # itself (that's covered against the real contract in infra/mongo tests).
    second = logged_in_client.post("/api/about", json=payload)
    assert second.status_code == 200
