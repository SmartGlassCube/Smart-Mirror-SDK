"""The routing table from infra/mongo/CONTRACT.md, in code.

Only `status == "published"` documents ever reach the mirror -- not just in
the widgets below, but in `sync.py` (nothing non-published is ever written
to the cache or indexed into Qdrant). Past events and expired announcements
leave their widget but stay searchable (RAG), per the contract.
"""

from datetime import datetime, timezone

from . import templates

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def is_published(doc: dict) -> bool:
    return doc.get("status") == "published"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


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


def mission_body(about_docs: list[dict]) -> str:
    """The `about` doc with key == "mission", or "" if not published/present."""
    for doc in about_docs:
        if is_published(doc) and doc.get("key") == "mission":
            return doc.get("body", "")
    return ""


def build_prompt_block(events: list[dict], announcements: list[dict], about_docs: list[dict], now: datetime = None) -> str:
    """Next 5 events, active announcements (high priority first), and the mission -- for the assistant's system prompt."""
    now = now or datetime.now(timezone.utc)
    sections = []

    next_events = upcoming_events(events, now)[:5]
    if next_events:
        lines = "\n".join(f"- {templates.render_event(e)}" for e in next_events)
        sections.append(f"Upcoming events:\n{lines}")

    actives = active_announcements(announcements, now)
    if actives:
        lines = "\n".join(f"- {templates.render_announcement(a)}" for a in actives)
        sections.append(f"Active announcements:\n{lines}")

    mission = mission_body(about_docs)
    if mission:
        sections.append(f"About IEEE INSAT:\n{mission}")

    return "\n\n".join(sections)
