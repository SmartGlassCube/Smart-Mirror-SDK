"""The routing table from infra/mongo/CONTRACT.md (Dashboard repo), in code.

Only `status == "published"` documents ever reach the mirror -- not just in
the widgets below, but in `sync.py` (nothing non-published is ever written
to the cache or indexed into Qdrant). Past events and expired announcements
leave their widget but stay searchable (RAG), per the contract.
"""

from datetime import datetime, timedelta, timezone

from . import templates

# A multi-day event is listed on each of its days, up to this many.
MAX_EVENT_DAYS = 31

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def is_published(doc: dict) -> bool:
    return doc.get("status") == "published"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def chapter_names(chapter_docs: list[dict]) -> dict:
    """{key: name} of the published chapters."""
    return {doc["key"]: doc["name"] for doc in chapter_docs if is_published(doc)}


def upcoming_events(events: list[dict], now: datetime = None) -> list[dict]:
    """Published events with start >= now, soonest first."""
    now = now or datetime.now(timezone.utc)
    upcoming = [e for e in events if is_published(e) and _aware(e["start"]) >= now]
    return sorted(upcoming, key=lambda e: _aware(e["start"]))


def active_announcements(announcements: list[dict], now: datetime = None) -> list[dict]:
    """Published announcements with publish_at <= now < expires_at, high priority first."""
    now = now or datetime.now(timezone.utc)
    active = []
    for a in announcements:
        if not is_published(a):
            continue
        if _aware(a["publish_at"]) > now:
            continue
        expires_at = a.get("expires_at")
        if expires_at is not None and now >= _aware(expires_at):
            continue
        active.append(a)
    return sorted(active, key=lambda a: (_PRIORITY_RANK.get(a.get("priority"), 1), _aware(a["publish_at"])))


def events_by_day(events: list[dict], chapters: dict = None) -> dict:
    """Every published event (past ones too), keyed by local day: {"2026-10-28": [event, ...]}.

    Days are in the mirror's timezone (Africa/Tunis); a multi-day event is
    listed on each of its days. Each day's events are soonest first, as
    JSON-ready dicts: id, title, start/end (ISO, local time), location,
    chapter (key) and chapter_name (None for the whole Student Branch).
    """
    days = {}
    for event in sorted((e for e in events if is_published(e)), key=lambda e: _aware(e["start"])):
        start = templates.to_local(event["start"])
        end = templates.to_local(event["end"]) if event.get("end") else None
        item = {
            "id": f"events:{event.get('_id')}",
            "title": event["title"],
            "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "location": event.get("location"),
            "chapter": event.get("chapter"),
            "chapter_name": templates.chapter_name(event, chapters),
        }
        last_day = end.date() if end and end.date() > start.date() else start.date()
        day = start.date()
        while day <= last_day and (day - start.date()).days < MAX_EVENT_DAYS:
            days.setdefault(day.isoformat(), []).append(item)
            day += timedelta(days=1)
    return days


def event_cards(events: list[dict], chapters: dict = None, now: datetime = None) -> list[dict]:
    """Every published event for the events page: upcoming soonest first, then past ones, most recent first.

    An event is past once it has ended (its start, if it has no end). Cards are
    JSON-ready: id, name, description, image (the event's image_url, or None),
    date (ISO, local time), chapter_name (None for the whole SB) and past.
    """
    now = now or datetime.now(timezone.utc)
    published = [e for e in events if is_published(e)]
    is_past = lambda e: _aware(e.get("end") or e["start"]) < now  # noqa: E731
    upcoming = sorted((e for e in published if not is_past(e)), key=lambda e: _aware(e["start"]))
    past = sorted((e for e in published if is_past(e)), key=lambda e: _aware(e["start"]), reverse=True)
    return [
        {
            "id": f"events:{e.get('_id')}",
            "name": e["title"],
            "description": e["description"],
            "image": e.get("image_url"),
            "date": templates.to_local(e["start"]).isoformat(),
            "chapter_name": templates.chapter_name(e, chapters),
            "past": is_past(e),
        }
        for e in upcoming + past
    ]


def news_items(announcements: list[dict], achievements: list[dict], chapters: dict = None, now: datetime = None) -> list[dict]:
    """The News widget's feed: active announcements (high priority first), then achievements, newest first."""
    items = [
        {
            "id": f"announcements:{a.get('_id')}",
            "kind": "announcement",
            "title": a["title"],
            "body": a["body"],
            "date": templates.to_local(a["publish_at"]).isoformat(),
            "priority": a.get("priority", "normal"),
            "chapter": a.get("chapter"),
            "chapter_name": templates.chapter_name(a, chapters),
        }
        for a in active_announcements(announcements, now)
    ]
    published = sorted((a for a in achievements if is_published(a)), key=lambda a: _aware(a["date"]), reverse=True)
    items += [
        {
            "id": f"achievements:{a.get('_id')}",
            "kind": "achievement",
            "title": a["title"],
            "body": a["description"],
            "date": templates.to_local(a["date"]).isoformat(),
            "priority": None,
            "chapter": a.get("chapter"),
            "chapter_name": templates.chapter_name(a, chapters),
        }
        for a in published
    ]
    return items


def mission_body(about_docs: list[dict]) -> str:
    """The `about` doc with key == "mission", or "" if not published/present."""
    for doc in about_docs:
        if is_published(doc) and doc.get("key") == "mission":
            return doc.get("body", "")
    return ""


def build_prompt_block(
    events: list[dict],
    announcements: list[dict],
    about_docs: list[dict],
    now: datetime = None,
    chapter_docs: list[dict] = None,
) -> str:
    """Next 5 events, active announcements (high priority first), the mission and the chapters -- for the assistant's system prompt."""
    now = now or datetime.now(timezone.utc)
    chapters = chapter_names(chapter_docs or [])
    sections = []

    next_events = upcoming_events(events, now)[:5]
    if next_events:
        lines = "\n".join(f"- {templates.render_event(e, chapters)}" for e in next_events)
        sections.append(f"Upcoming events:\n{lines}")

    actives = active_announcements(announcements, now)
    if actives:
        lines = "\n".join(f"- {templates.render_announcement(a, chapters)}" for a in actives)
        sections.append(f"Active announcements:\n{lines}")

    mission = mission_body(about_docs)
    if mission:
        sections.append(f"About IEEE INSAT:\n{mission}")

    if chapters:
        sections.append(f"IEEE INSAT Student Branch chapters: {', '.join(sorted(chapters.values()))}.")

    return "\n\n".join(sections)
