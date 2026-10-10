"""Renders a Mongo content record into clean English text for embedding.

One function per collection. Never include internal fields (_id, status,
created_at, updated_at, updated_by) -- the assistant reads this text aloud
as if it were a fact about the club, so it must read as prose, not data.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MIRROR_TZ = ZoneInfo("Africa/Tunis")


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MIRROR_TZ)


def render_datetime(value: datetime) -> str:
    return _local(value).strftime("%A, %B %-d, %Y at %H:%M")


def render_event(doc: dict) -> str:
    parts = [f"Event: {doc['title']}.", f"Date: {render_datetime(doc['start'])}."]
    if doc.get("location"):
        parts.append(f"Location: {doc['location']}.")
    if doc.get("description"):
        parts.append(doc["description"])
    return " ".join(parts)


def render_announcement(doc: dict) -> str:
    parts = [f"Announcement: {doc['title']}.", doc["body"]]
    return " ".join(parts)


def render_about(doc: dict) -> str:
    return f"{doc['title']}: {doc['body']}"


def render_achievement(doc: dict) -> str:
    return f"Achievement: {doc['title']}, on {render_datetime(doc['date'])}. {doc['description']}"


def render_board(doc: dict) -> str:
    return f"{doc['name']} is the {doc['role']} of the IEEE INSAT board for the {doc['term']} term."


_RENDERERS = {
    "events": render_event,
    "announcements": render_announcement,
    "about": render_about,
    "achievements": render_achievement,
    "board": render_board,
}


def render(collection: str, doc: dict) -> str:
    """Render any document from `collection` (one of config.COLLECTIONS) to text."""
    renderer = _RENDERERS.get(collection)
    if renderer is None:
        raise ValueError(f"no template for collection {collection!r}")
    return renderer(doc)
