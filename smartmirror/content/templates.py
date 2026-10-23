"""Renders a Mongo content record into clean English text for embedding.

One function per collection. Never include internal fields (_id, status,
created_at, updated_at, updated_by) -- the assistant reads this text aloud
as if it were a fact about the club, so it must read as prose, not data.

Content may belong to a chapter (contract v0.5: `chapter` = a chapters `key`,
absent = the whole Student Branch). Renderers take `chapters`, a
{key: name} map, to name it; an unknown key is shown as-is.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MIRROR_TZ = ZoneInfo("Africa/Tunis")

# Bump whenever a renderer's output changes: content sync then re-indexes every
# doc once, instead of only the ones edited since (see ContentSync._check_embedding_model).
TEMPLATE_VERSION = 3


def to_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MIRROR_TZ)


def render_datetime(value: datetime) -> str:
    return to_local(value).strftime("%A, %B %-d, %Y at %H:%M")


def render_end(start: datetime, end: datetime) -> str:
    """Just the time when the event ends the day it starts, else the full date."""
    if to_local(start).date() == to_local(end).date():
        return to_local(end).strftime("%H:%M")
    return render_datetime(end)


def chapter_name(doc: dict, chapters: dict = None):
    """The name of the chapter `doc` belongs to, or None for the whole Student Branch."""
    key = doc.get("chapter")
    if not key:
        return None
    return (chapters or {}).get(key, key)


def _label(kind: str, doc: dict, chapters: dict) -> str:
    """ "Event" for the whole SB, "Computer Society chapter event" for a chapter's."""
    name = chapter_name(doc, chapters)
    return f"{name} chapter {kind.lower()}" if name else kind


def render_chapter(doc: dict, chapters: dict = None) -> str:
    return f"Chapter: the IEEE INSAT {doc['name']} chapter. {doc['description']}"


def render_event(doc: dict, chapters: dict = None) -> str:
    parts = [f"{_label('Event', doc, chapters)}: {doc['title']}.", f"Date: {render_datetime(doc['start'])}."]
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


def render_announcement(doc: dict, chapters: dict = None) -> str:
    kind = "Important announcement" if doc.get("priority") == "high" else "Announcement"
    parts = [f"{_label(kind, doc, chapters)}: {doc['title']}.", doc["body"]]
    if doc.get("publish_at"):
        parts.append(f"Posted on {render_datetime(doc['publish_at'])}.")
    if doc.get("expires_at"):
        parts.append(f"Valid until {render_datetime(doc['expires_at'])}.")
    return " ".join(parts)


def render_about(doc: dict, chapters: dict = None) -> str:
    return f"{doc['title']}: {doc['body']}"


def render_achievement(doc: dict, chapters: dict = None) -> str:
    return (
        f"{_label('Achievement', doc, chapters)}: {doc['title']}, on {render_datetime(doc['date'])}. "
        f"{doc['description']}"
    )


def render_board(doc: dict, chapters: dict = None) -> str:
    name = chapter_name(doc, chapters)
    board = f"IEEE INSAT {name} chapter board" if name else "IEEE INSAT Student Branch board"
    text = f"{doc['name']} is the {doc['role']} of the {board} for the {doc['term']} term."
    if doc.get("email"):
        text += f" Contact: {doc['email']}."
    return text


_RENDERERS = {
    "chapters": render_chapter,
    "events": render_event,
    "announcements": render_announcement,
    "about": render_about,
    "achievements": render_achievement,
    "board": render_board,
}


def render(collection: str, doc: dict, chapters: dict = None) -> str:
    """Render any document from `collection` (one of config.COLLECTIONS) to text.

    `chapters` maps chapter key -> name, to name the chapter a doc belongs to.
    """
    renderer = _RENDERERS.get(collection)
    if renderer is None:
        raise ValueError(f"no template for collection {collection!r}")
    return renderer(doc, chapters)
