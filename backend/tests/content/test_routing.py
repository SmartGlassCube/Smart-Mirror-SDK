from datetime import datetime, timedelta, timezone

from glasscube.content import routing

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


def test_events_by_day_keys_events_by_local_day():
    late = datetime(2026, 3, 9, 23, 30, tzinfo=timezone.utc)  # already March 10 in Tunis (UTC+1)
    days = routing.events_by_day([
        _event(_id="a", title="Late talk", start=late, location="Amphi A", chapter="cs"),
        _event(_id="b", title="Morning", start=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)),
        _event(_id="c", title="Draft", status="draft", start=late),
    ], {"cs": "Computer Society"})

    assert list(days) == ["2026-03-10"]
    assert [e["title"] for e in days["2026-03-10"]] == ["Late talk", "Morning"]
    assert days["2026-03-10"][0] == {
        "id": "events:a", "title": "Late talk", "start": "2026-03-10T00:30:00+01:00", "end": None,
        "location": "Amphi A", "chapter": "cs", "chapter_name": "Computer Society",
    }
    assert days["2026-03-10"][1]["chapter_name"] is None  # whole SB


def test_events_by_day_keeps_past_events_and_spreads_multi_day_ones():
    days = routing.events_by_day([
        _event(title="Old", start=NOW - timedelta(days=30)),
        _event(title="Hackathon", start=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
               end=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc)),
    ])

    assert "2025-12-02" in days
    assert [day for day, events in days.items() if events[0]["title"] == "Hackathon"] == [
        "2026-03-10", "2026-03-11", "2026-03-12",
    ]


def test_news_items_are_active_announcements_then_newest_achievements():
    news = routing.news_items(
        [_announcement(title="Normal"), _announcement(title="Urgent", priority="high"),
         _announcement(title="Expired", expires_at=NOW - timedelta(hours=1))],
        [{"status": "published", "title": "Older win", "description": "d", "date": NOW - timedelta(days=60)},
         {"status": "published", "title": "Newer win", "description": "d", "date": NOW - timedelta(days=5), "chapter": "cs"},
         {"status": "draft", "title": "Draft win", "description": "d", "date": NOW}],
        {"cs": "Computer Society"},
        NOW,
    )

    assert [(n["kind"], n["title"]) for n in news] == [
        ("announcement", "Urgent"), ("announcement", "Normal"),
        ("achievement", "Newer win"), ("achievement", "Older win"),
    ]
    assert news[2]["chapter_name"] == "Computer Society"


def test_build_prompt_block_lists_the_chapters_and_labels_chapter_events():
    chapters = [
        {"status": "published", "key": "cs", "name": "Computer Society"},
        {"status": "published", "key": "ras", "name": "Robotics and Automation Society"},
        {"status": "draft", "key": "pes", "name": "Power and Energy Society"},
    ]
    block = routing.build_prompt_block([_event(title="Workshop", chapter="cs")], [], [], NOW, chapter_docs=chapters)

    assert "Computer Society chapter event: Workshop." in block
    assert "IEEE INSAT Student Branch chapters: Computer Society, Robotics and Automation Society." in block
    assert "Power and Energy" not in block


def test_event_cards_list_every_event_upcoming_first_then_past_newest_first():
    cards = routing.event_cards([
        _event(_id="old", title="Old", start=NOW - timedelta(days=60)),
        _event(_id="later", title="Later", start=NOW + timedelta(days=10), image_url="https://example.com/later.png"),
        _event(_id="recent", title="Recent", start=NOW - timedelta(days=2)),
        _event(_id="soon", title="Soon", start=NOW + timedelta(days=1), chapter="cs"),
        _event(_id="ongoing", title="Ongoing", start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=2)),
        _event(_id="draft", title="Draft", status="draft"),
    ], {"cs": "Computer Society"}, NOW)

    assert [c["name"] for c in cards] == ["Ongoing", "Soon", "Later", "Recent", "Old"]
    assert [c["past"] for c in cards] == [False, False, False, True, True]
    assert cards[2]["image"] == "https://example.com/later.png"
    assert cards[1]["image"] is None  # the page shows the "?" placeholder
    assert cards[1]["chapter_name"] == "Computer Society"
    assert cards[1]["date"] == "2026-01-02T01:00:00+01:00"
