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


def test_render_event_includes_end_tags_and_registration():
    doc = {
        "title": "Workshop", "description": "A hands-on workshop.",
        "start": datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        "tags": ["AI", "robotics"], "registration_url": "https://example.com/register",
        "image_url": "https://example.com/poster.png",
    }
    text = templates.render("events", doc)
    assert "Ends: 13:00." in text  # same day: just the (Africa/Tunis) time
    assert "Topics: AI, robotics." in text
    assert "Registration: https://example.com/register." in text
    assert "poster" not in text  # a poster image means nothing read aloud


def test_render_event_ending_another_day_gives_the_full_end_date():
    doc = {
        "title": "Hackathon", "description": "48 hours.",
        "start": datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc),
    }
    assert "Ends: Tuesday, November 3, 2026 at 10:00." in templates.render("events", doc)


def test_render_announcement_includes_priority_and_dates():
    doc = {
        "title": "Renewal", "body": "Membership renewal is open.", "priority": "high",
        "publish_at": datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc),
    }
    text = templates.render("announcements", doc)
    assert text.startswith("Important announcement: Renewal.")
    assert "Posted on Thursday, October 1, 2026 at 09:00." in text
    assert "Valid until Saturday, October 31, 2026 at 23:00." in text


def test_render_board_includes_email_when_given():
    doc = {"name": "Sara", "role": "Chair", "term": "2026-2027", "email": "chair@example.com"}
    assert templates.render("board", doc).endswith("Contact: chair@example.com.")
