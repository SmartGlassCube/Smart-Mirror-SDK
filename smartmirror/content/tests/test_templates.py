from datetime import datetime, timezone

from smartmirror.content import templates


def test_render_event_excludes_internal_fields():
    doc = {
        "_id": "abc", "status": "published", "updated_by": "someone",
        "title": "Workshop", "description": "A hands-on workshop.",
        "start": datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc), "location": "INSAT",
    }
    text = templates.render("events", doc)
    assert "Workshop" in text
    assert "A hands-on workshop." in text
    assert "INSAT" in text
    assert "_id" not in text and "abc" not in text
    assert "someone" not in text
    assert "status" not in text and "published" not in text


def test_render_announcement():
    doc = {"title": "Renewal", "body": "Membership renewal is open."}
    text = templates.render("announcements", doc)
    assert "Renewal" in text and "Membership renewal is open." in text


def test_render_about():
    doc = {"key": "mission", "title": "Mission", "body": "We teach things."}
    text = templates.render("about", doc)
    assert "Mission" in text and "We teach things." in text


def test_render_unknown_collection_raises():
    import pytest
    with pytest.raises(ValueError):
        templates.render("not_a_collection", {})
