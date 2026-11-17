"""The demo mirror `glasscube` opens with no arguments: Smart Mirror Studio's demo project.

demo.glasscube.json is the studio's "Demo mirror" (New -> Demo project), exported as is;
re-export it from the studio to change it.
"""

from datetime import date, datetime
from pathlib import Path

from ..project import Project, load_project

DEMO_FILE = Path(__file__).with_name("demo.glasscube.json")


def demo_project(today=None) -> Project:
    project = load_project(DEMO_FILE)
    _move_calendar_to(project, today or date.today())
    return project


def _move_calendar_to(project: Project, today: date) -> None:
    """The demo's agenda has fixed dates from the day it was exported: shift them so the first one is today."""
    for page in project.pages:
        for widget in page.get("widgets", []):
            source = widget.get("data") or {}
            events = (source.get("value") or {}).get("events") if source.get("kind") == "static" else None
            if widget.get("type") != "calendar" or not isinstance(events, list) or not events:
                continue
            starts = [datetime.fromisoformat(event["start"]) for event in events]
            shift = today - min(starts).date()
            for event, start in zip(events, starts):
                event["start"] = (start + shift).isoformat()
