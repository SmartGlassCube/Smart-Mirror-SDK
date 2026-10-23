"""Renders a Mongo content record into clean English text for embedding.

One function per collection. Never include internal fields (_id, status,
created_at, updated_at, updated_by) -- the assistant reads this text aloud
as if it were a fact about the club, so it must read as prose, not data.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MIRROR_TZ = ZoneInfo("Africa/Tunis")

# Bump whenever a renderer's output changes: content sync then re-indexes every
# doc once, instead of only the ones edited since (see ContentSync._check_embedding_model).
TEMPLATE_VERSION = 2


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MIRROR_TZ)


def render_datetime(value: datetime) -> str:
    return _local(value).strftime("%A, %B %-d, %Y at %H:%M")


def render_end(start: datetime, end: datetime) -> str:
    """Just the time when the event ends the day it starts, else the full date."""
    if _local(start).date() == _local(end).date():
        return _local(end).strftime("%H:%M")
    return render_datetime(end)


def render_event(doc: dict) -> str:
    parts = [f"Event: {doc['title']}.", f"Date: {render_datetime(doc['start'])}."]
    if doc.get("end"):
        parts.append(f"Ends: {render_end(doc['start'], doc['end'])}.")
    if doc.get("location"):
        parts.append(f"Location: {doc['location']}.")
    if doc.get("tags"):
        parts.append(f"Topics: {', '.join(doc['tags'])}.")
    if doc.get("description"):
        parts.append(doc["description"])
    if doc.get("registration_url"):
        parts.append(f"Registration: {doc['registration_url']}.")
    return " ".join(parts)


def render_announcement(doc: dict) -> str:
    label = "Important announcement" if doc.get("priority") == "high" else "Announcement"
    parts = [f"{label}: {doc['title']}.", doc["body"]]
    if doc.get("publish_at"):
        parts.append(f"Posted on {render_datetime(doc['publish_at'])}.")
    if doc.get("expires_at"):
        parts.append(f"Valid until {render_datetime(doc['expires_at'])}.")
    return " ".join(parts)


def render_about(doc: dict) -> str:
    return f"{doc['title']}: {doc['body']}"


def render_achievement(doc: dict) -> str:
    return f"Achievement: {doc['title']}, on {render_datetime(doc['date'])}. {doc['description']}"


def render_board(doc: dict) -> str:
    text = f"{doc['name']} is the {doc['role']} of the IEEE INSAT board for the {doc['term']} term."
    if doc.get("email"):
        text += f" Contact: {doc['email']}."
    return text


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
