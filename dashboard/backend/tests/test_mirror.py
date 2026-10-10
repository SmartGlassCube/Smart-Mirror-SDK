from datetime import datetime, timedelta, timezone


def test_mirror_status_online_flag(logged_in_client, db):
    now = datetime.now(timezone.utc)
    db.mirror_status.insert_one({
        "mirror_id": "mirror-1", "last_seen": now, "uptime_s": 120.0,
        "current_page": "home", "last_sync_at": now, "last_error": None, "updated_at": now,
    })
    db.mirror_status.insert_one({
        "mirror_id": "mirror-stale", "last_seen": now - timedelta(minutes=10), "uptime_s": 5.0,
        "current_page": None, "last_sync_at": None, "last_error": "boom", "updated_at": now,
    })

    resp = logged_in_client.get("/api/mirror/status")
    assert resp.status_code == 200
    by_id = {m["mirror_id"]: m for m in resp.json()}
    assert by_id["mirror-1"]["online"] is True
    assert by_id["mirror-stale"]["online"] is False
    assert by_id["mirror-stale"]["last_error"] == "boom"


def test_mirror_status_requires_auth(client):
    resp = client.get("/api/mirror/status")
    assert resp.status_code == 401
