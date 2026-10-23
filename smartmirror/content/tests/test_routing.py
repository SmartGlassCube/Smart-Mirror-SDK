from datetime import datetime, timedelta, timezone

from smartmirror.content import routing

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event(**overrides):
    doc = {"status": "published", "title": "E", "description": "d", "start": NOW + timedelta(days=1)}
    doc.update(overrides)
    return doc


def _announcement(**overrides):
    doc = {
        "status": "published", "title": "A", "body": "b", "priority": "normal",
        "publish_at": NOW - timedelta(days=1), "expires_at": NOW + timedelta(days=1),
    }
    doc.update(overrides)
    return doc


def test_upcoming_events_filters_past_and_draft():
    events = [
        _event(title="past", start=NOW - timedelta(days=1)),
        _event(title="draft", status="draft", start=NOW + timedelta(days=1)),
        _event(title="future", start=NOW + timedelta(days=1)),
    ]
    result = routing.upcoming_events(events, now=NOW)
    assert [e["title"] for e in result] == ["future"]


def test_upcoming_events_sorted_soonest_first():
    events = [_event(title="later", start=NOW + timedelta(days=5)), _event(title="sooner", start=NOW + timedelta(days=1))]
    result = routing.upcoming_events(events, now=NOW)
    assert [e["title"] for e in result] == ["sooner", "later"]


def test_active_announcements_filters_not_yet_published_and_expired():
    announcements = [
        _announcement(title="future", publish_at=NOW + timedelta(days=1)),
        _announcement(title="expired", publish_at=NOW - timedelta(days=10), expires_at=NOW - timedelta(days=1)),
        _announcement(title="draft", status="draft"),
        _announcement(title="active"),
    ]
    result = routing.active_announcements(announcements, now=NOW)
    assert [a["title"] for a in result] == ["active"]


def test_active_announcements_no_expiry_never_expires():
    announcements = [_announcement(title="forever", expires_at=None)]
    result = routing.active_announcements(announcements, now=NOW + timedelta(days=365))
    assert [a["title"] for a in result] == ["forever"]


def test_active_announcements_high_priority_first():
    announcements = [
        _announcement(title="normal", priority="normal"),
        _announcement(title="high", priority="high"),
        _announcement(title="low", priority="low"),
    ]
    result = routing.active_announcements(announcements, now=NOW)
    assert [a["title"] for a in result] == ["high", "normal", "low"]


def test_mission_body_only_published_mission_key():
    about_docs = [
        {"status": "published", "key": "contact", "body": "contact info"},
        {"status": "draft", "key": "mission", "body": "draft mission"},
        {"status": "published", "key": "mission", "body": "real mission"},
    ]
    assert routing.mission_body(about_docs) == "real mission"


def test_build_prompt_block_includes_next_five_events_only():
    events = [_event(title=f"e{i}", start=NOW + timedelta(days=i)) for i in range(1, 8)]
    block = routing.build_prompt_block(events, [], [], now=NOW)
    for i in range(1, 6):
        assert f"e{i}" in block
    for i in range(6, 8):
        assert f"e{i}" not in block
